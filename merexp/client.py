from __future__ import annotations
import requests
from io import BytesIO
from typing import Any, Dict, Optional, List, Literal
import pandas as pd
import os
from .utils import get_sequence_lengths
import json

class MeromeExplorerClient:
    def __init__(self, base_url: str = "https://openquery-dev.curie.fr", api_key: str = None, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()

    # -------------------------
    # Internal request helper
    # -------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict] = None,
        json: Any = None,
        data: Any = None,
        files: Any = None,
    ) -> Dict:
        url = f"{self.base_url}{path}"

        params = params or {}
        params["key"] = self.api_key

        resp = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json,
            data=data,
            files=files,
            timeout=self.timeout,
        )

        if not resp.ok:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            raise RuntimeError(f"{resp.status_code}: {err}")

        if resp.status_code == 204:
            return {}

        content_type = resp.headers.get("Content-Type", "").split(";")[0]

        if content_type == "application/json":
            return resp.json()

        if content_type == "text/csv":
            return pd.read_csv(BytesIO(resp.content))

        if content_type.startswith("text/"):
            return resp.text

        return resp.content

    # =========================================================
    # Billing
    # =========================================================

    def estimate_billing(
            self, 
            file_path: str, 
            indices: List[str],
            profile: bool = False, 
            window_size: int = 30, 
            step_size: int = 1,
    ):
        """POST /api/v1/billing/estimate"""

        sequence_lengths = get_sequence_lengths(file_path)

        datasets = self.list_datasets(output="json")

        records = []
        for d in datasets:
            records.extend(d["indices"])
        records = pd.DataFrame.from_records(records)

        if set(indices) - set(records["api_id"]):
            raise ValueError(f"Requested indices {set(indices) - set(records['api_id'])} not available")

        subindex_count = sum(records["subindex_count"][records["api_id"].isin(indices)])

        params = {
            "sequence_lengths": sequence_lengths,
            "subindex_count": subindex_count,
        }
        if profile:
            params["profiling_options"] = {
                "chunk_size": window_size,
                "step_size": step_size,
            }

        return self._request("POST", "/api/v1/billing/estimate", json=params)

    def get_consumption(self):
        """GET /api/v1/billing/consumption"""
        resp =  self._request("GET", "/api/v1/billing/consumption")
        if resp["profile"].startswith("Anonymous"):
            resp["profile"] = "Anonymous"
        return resp

    # =========================================================
    # Datasets
    # =========================================================

    def list_datasets(self, output: Literal["json", "txt"] = "txt"):
        """GET /api/v1/core/datasets"""
        datasets =  self._request("GET", "/api/v1/core/datasets")

        if output == "json":
            return datasets
        
        lines = []

        for dataset in datasets:
            lines.append(
                f"\n{dataset['api_id']} ({len(dataset['indices'])} indices)"
            )
            lines.append("-" * 60)

            for idx in sorted(
                dataset["indices"],
                key=lambda x: x["sample_count"],
                reverse=True,
            ):
                lines.append(
                    f"{idx['api_id']:15} "
                    f"samples={idx['sample_count']:5d} "
                    f"subindices={idx['subindex_count']:2d}"
                )

        print("\n".join(lines))

        return

    def get_dataset_info(self, dataset: str):
        """GET /api/v1/core/datasets/{dataset_id}"""
        datasets = self.list_datasets(output="json")
        for d in datasets:
            if d["api_id"] == dataset:
                return pd.DataFrame.from_records(d["indices"])    
        raise ValueError(f"Dataset not found. Available datasets: {[d['api_id'] for d in datasets]}")

    def get_index_metadata(self, api_id: str):
        """GET /api/v1/core/indices/{api_id}/metadata"""
        return self._request("GET", f"/api/v1/core/indices/{api_id}/metadata")
    
    # =========================================================
    # Queries
    # =========================================================

    def start_query(
            self, 
            file_path: str, 
            indices: List[str], 
            query_name: str = None,
            email: str = None, 
            retention_days: int = 2,
            profile: bool = False, 
            window_size: int = 30, 
            step_size: int = 1,
        ):
        """
        POST /api/v1/core/queries
        multipart/form-data:
          - file: binary
          - params: JSON object
        """

        if not os.path.exists(file_path):
            raise ValueError(f"File {file_path} does not exist.")
        
        datasets = self.list_datasets(output="json")

        records = []
        for d in datasets:
            records.extend(d["indices"])
        records = pd.DataFrame.from_records(records)

        if set(indices) - set(records["api_id"]):
            raise ValueError(f"Requested indices {set(indices) - set(records['api_id'])} not available")
        
        indices = records["id"][records["api_id"].isin(indices)].tolist()

        params = {
            "indices": indices,
            "retention_days": retention_days,
        }

        if email:
            params["email"] = email

        if query_name:
            params["name"] = query_name

        if profile:
            params["profiling_options"] = {
                "chunk_size": window_size,
                "step_size": step_size,
            }
  
        with open(file_path, "rb") as f:
            files = {
                "file": f,
                "params": (None, json.dumps(params), "application/json"),
            }
            response = self._request("POST", "/api/v1/core/queries", files=files)

        return response["id"]

    def get_query(self, query_id: str):
        """GET /api/v1/core/queries/{query_id}"""
        return self._request("GET", f"/api/v1/core/queries/{query_id}")

    def update_query(self, query_id: str, retention_days: int = None, public: bool = None):
        """PATCH /api/v1/core/queries/{query_id}"""

        params = {}
        if retention_days:
            params["retention_days"] = retention_days
        if public:
            params["public"] = public

        return self._request("PATCH", f"/api/v1/core/queries/{query_id}", json=params)

    def download_results(self, query_id: str, output: str = "results.zip"):
        """GET /api/v1/core/queries/{query_id}/results/{filename}"""
        
        response_bytes =  self._request(
            "GET",
            f"/api/v1/core/queries/{query_id}/results/results.zip",
        )
        with open(output, "wb") as f:
            f.write(response_bytes)

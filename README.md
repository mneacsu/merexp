# merexp

A lightweight Python client for interacting with the **[Merome Explorer API](https://openquery-dev.curie.fr/api/v1/docs)**.

The client provides a simple interface for browsing available datasets, submitting sequence queries, estimating query costs, monitoring query status,and downloading results.

## Installation

Install from source:

```bash
git clone https://github.com/mneacsu/merexp.git
cd merexp
pip install .
```

## Quick Start

```python
from merexp import MeromeExplorerClient

client = MeromeExplorerClient()
```

If you have an API key:
```python
client = MeromeExplorerClient(api_key="your_api_key")
```

## Examples

### List available datasets

```python
client.list_datasets()
```

### Estimate query cost

```python
client.estimate_billing(file_path="sequences.fasta", indices=["TCGA-STAD", "CPTAC-STAD"], profile = False)
```

### Submit a query

```python
query_id = client.start_query(
    file_path="sequences.fasta",
    indices=["TCGA-STAD", "CPTAC-STAD"],
    profile=True,
    window_size=30,
    step_size=5,
    email= "user@example.com",
)
```

### Check query status

```python
status = client.get_query(query_id)
```

### Download results

```python
client.download_results(
    query_id,
    "results.zip",
)
```

### Retrieve sample metadata

```python
metadata = client.get_index_metadata("TCGA-BRCA")
```

## Available Methods

### Billing

* `estimate_billing()`
* `get_consumption()`

### Datasets

* `list_datasets()`
* `get_dataset()`
* `get_index_metadata()`

### Queries

* `start_query()`
* `get_query()`
* `update_query()`
* `download_results()`

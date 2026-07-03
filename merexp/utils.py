import subprocess

def get_sequence_lengths(path):
    awk_script = r"""
    /^>/ {
        if (len) print len
        len = 0
        next
    }
    {
        len += length($0)
    }
    END {
        print len
    }
    """

    result = subprocess.run(
        ["awk", awk_script, path],
        capture_output=True,
        text=True,
        check=True,
    )

    return [int(x) for x in result.stdout.splitlines() if x.strip()]
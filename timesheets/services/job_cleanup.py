from difflib import SequenceMatcher
from django.db.models import Q
from ..models import Job, TimeEntry
from .importer import valid_time_entry_job_qs


def normalized_job_number(value):
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def invalid_job_qs():
    """Jobs that were created from bad/free-form job numbers.

    Current business rule: an invalid job record has no description.
    """
    return Job.objects.filter(description="").order_by("job_number")


def entries_for_invalid_job(job):
    return TimeEntry.objects.filter(Q(job=job) | Q(job_number__iexact=job.job_number))


def valid_replacement_jobs():
    return valid_time_entry_job_qs().order_by("job_number")


def suggest_replacement_jobs(invalid_job_number, limit=5):
    """Return likely valid replacement jobs for an invalid job number.

    Uses only Python stdlib so it works on SQLite/Postgres without extensions.
    Scores favor exact normalized prefix matches, containment, and fuzzy
    similarity between job numbers.
    """
    raw = (invalid_job_number or "").strip()
    norm = normalized_job_number(raw)
    if not norm:
        return []

    scored = []
    for job in valid_replacement_jobs().only("id", "job_number", "description"):
        candidate_raw = job.job_number or ""
        candidate_norm = normalized_job_number(candidate_raw)
        if not candidate_norm:
            continue

        score = 0
        if candidate_norm == norm:
            score = 100
        elif candidate_norm.startswith(norm):
            score = 95
        elif norm.startswith(candidate_norm):
            score = 90
        elif norm in candidate_norm or candidate_norm in norm:
            score = 82
        else:
            score = int(SequenceMatcher(None, norm, candidate_norm).ratio() * 100)

        # Small boost for same first 3+ characters. This helps job-family typos.
        if len(norm) >= 3 and candidate_norm.startswith(norm[:3]):
            score = min(100, score + 5)

        if score >= 45:
            scored.append((score, job))

    scored.sort(key=lambda item: (-item[0], item[1].job_number))
    return scored[:limit]


def cleanup_invalid_job(job, replacement_job=None):
    """Clear or reassign all entries for invalid job, then delete it.

    replacement_job=None means convert entries to internal/no-job work.
    Returns number of updated TimeEntry rows.
    """
    entries = entries_for_invalid_job(job)
    count = entries.count()
    if replacement_job is None:
        entries.update(job=None, job_number="")
    else:
        entries.update(job=replacement_job, job_number=replacement_job.job_number)
    job.delete()
    return count

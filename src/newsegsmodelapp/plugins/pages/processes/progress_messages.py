"""Progress messages shared by the processes of the pages.

Progress is a count: a procedure reports `(completed, total)`, the number of tasks completed out
of the total, before starting each task and when the last is done. A run of several model runs,
such as a DSA or a PSA, therefore names the run underway as `completed + 1`.
"""

def runs_progress_message(prefix: str, completed: int, total: int, elapsed_s: float) -> str:
    """The message of the progress of a sequence of model runs.

    Args:
        prefix: Start of the message, e.g. 'DSA (all configurations)'.
        completed: Number of runs completed.
        total: Number of runs.
        elapsed_s: Time (s) since the first run started.

    Returns:
        The message, e.g. 'DSA: Run 3 of 9, 1.2 sec/run. Elapsed time: 2 seconds.'
    """
    elapsed = f'Elapsed time: {elapsed_s:.0f} seconds.'
    if completed >= total:
        return f'{prefix}: {total} of {total} runs complete. {elapsed}'
    rate = f', {elapsed_s / completed:.1f} sec/run' if completed > 0 else ''
    return f'{prefix}: Run {completed + 1} of {total}{rate}. {elapsed}'

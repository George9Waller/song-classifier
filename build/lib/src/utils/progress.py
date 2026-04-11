from rich.progress import SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

PROGRESS_COLUMNS = [
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    TextColumn("[cyan]{task.fields[filename]}"),
]

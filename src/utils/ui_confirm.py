"""Textual TUI for confirming and editing track metadata."""

from typing import Optional

from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Label, Select, Checkbox
from textual.containers import Vertical

from src.data.models import AlbumMetadata, TrackMetadata
from src.data import get_album_metadata
from src.utils.constants import VARIOUS_ARTISTS


GENRE_OPTIONS: list[str] = [
    "House",
    "Techno",
    "Trance",
    "Drum & Bass",
    "Dubstep",
    "Hip-Hop",
    "Pop",
    "Rock",
    "Indie",
    "Electronic",
    "Ambient",
]


def _build_album_options(
    initial: TrackMetadata,
    albums: list[AlbumMetadata],
) -> tuple[list[tuple[str, str]], str]:
    """Build album select options and determine default value.

    Args:
        initial: Initial track metadata with album info.
        albums: List of known albums.

    Returns:
        Tuple of (options list, default value).
        Options are (label, value) tuples for the Select widget.
    """
    # Build options from known albums
    album_options = [(f"{a.name} ({a.artist})", a.name) for a in albums]

    # Always include create option
    album_options.append(("Create new...", "__create__"))

    # If initial album exists but isn't in options yet, insert it at the top
    option_values = [v for _, v in album_options]
    if initial.album and initial.album.name and initial.album.name not in option_values:
        initial_label = (
            f"{initial.album.name} ({initial.album.artist})"
            if initial.album.artist
            else initial.album.name
        )
        album_options.insert(0, (initial_label, initial.album.name))
        option_values.insert(0, initial.album.name)

    # Determine default value
    desired_default = initial.album.name if (initial.album and initial.album.name) else None
    if desired_default and desired_default in option_values:
        default_value = desired_default
    elif option_values:
        default_value = option_values[0]
    else:
        default_value = "__create__"

    return album_options, default_value


class ConfirmMetadataApp(App[TrackMetadata]):
    """Textual app for reviewing and confirming track metadata."""

    CSS = """
    Screen { align: center middle; }
    #form { width: 80; }
    Input, Select { margin: 1 0; }
    Button { margin-top: 1; }
    """

    def __init__(self, initial: TrackMetadata) -> None:
        """Initialize the app with initial metadata.

        Args:
            initial: Initial metadata to display for editing.
        """
        super().__init__()
        self.initial = initial
        self._result: Optional[TrackMetadata] = None

    def compose(self) -> ComposeResult:
        """Compose the UI widgets."""
        # Build genre options
        genre_options = list(GENRE_OPTIONS)
        if self.initial.genre and self.initial.genre not in genre_options:
            genre_options.insert(0, self.initial.genre)

        # Build album options
        albums = get_album_metadata()
        album_list = albums if isinstance(albums, list) else []
        album_options, default_album_value = _build_album_options(self.initial, album_list)

        yield Vertical(
            Label(f"File: {self.initial.key}"),
            Label("Review and confirm track metadata"),
            Label("Track"),
            Input(self.initial.track, placeholder="Track", id="track"),
            Label("Artist"),
            Input(self.initial.artist, placeholder="Artist", id="artist"),
            Label("Album"),
            Select(album_options, id="album_select", value=default_album_value),
            Input(
                self.initial.album.name, placeholder="New Album Name", id="album_name"
            ),
            Label("New Album Artist"),
            Input(
                self.initial.album.artist,
                placeholder="New Album Artist",
                id="album_artist",
            ),
            Checkbox(VARIOUS_ARTISTS, id="va_checkbox"),
            Label("Genre"),
            Select(
                ((g, g) for g in genre_options),
                id="genre",
                value=self.initial.genre or (genre_options[0] if genre_options else ""),
            ),
            Label("Date (YYYY or YYYY-MM-DD)"),
            Input(
                self.initial.date or "",
                placeholder="Date (YYYY or YYYY-MM-DD)",
                id="date",
            ),
            Button("Confirm", id="confirm"),
            id="form",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle confirm button press."""
        if event.button.id == "confirm":
            track = self.query_one("#track", Input).value or ""
            artist = self.query_one("#artist", Input).value or ""
            album_select = self.query_one("#album_select", Select)
            selected_album = album_select.value or ""

            if selected_album == "__create__":
                album_name = self.query_one("#album_name", Input).value or ""
                va_checked = self.query_one("#va_checkbox", Checkbox).value
                if va_checked:
                    album_artist = VARIOUS_ARTISTS
                else:
                    album_artist = (
                        self.query_one("#album_artist", Input).value or artist
                    )
            else:
                album_name = selected_album
                # Derive album artist from known albums
                known_album = get_album_metadata(key=selected_album)
                album_artist = (
                    getattr(known_album, "artist", None)
                    or getattr(self.initial.album, "artist", None)
                    or artist
                )

            genre = self.query_one("#genre", Select).value or ""
            date = self.query_one("#date", Input).value or None

            self._result = TrackMetadata(
                key=self.initial.key,
                track=track,
                artist=artist,
                album=AlbumMetadata(name=album_name, artist=album_artist),
                genre=genre,
                date=date,
            )
            self.exit(self._result)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle album select changes to show/hide create fields."""
        if event.select.id == "album_select":
            value = event.value or ""
            album_name_input = self.query_one("#album_name", Input)
            album_artist_input = self.query_one("#album_artist", Input)
            va_checkbox = self.query_one("#va_checkbox", Checkbox)

            if value == "__create__":
                # Show new album inputs
                album_name_input.display = True
                album_artist_input.display = True
                va_checkbox.display = True
                current_artist = self.query_one("#artist", Input).value or ""
                album_artist_input.value = current_artist
                va_checkbox.value = current_artist.strip().lower() == "various artists"
                album_artist_input.disabled = va_checkbox.value
            else:
                # Hide new album inputs
                album_name_input.display = False
                album_artist_input.display = False
                va_checkbox.display = False
                va_checkbox.value = False
                album_artist_input.disabled = False
                # Set album artist from known albums
                for a in (get_album_metadata() or []):
                    if a.name == value:
                        album_artist_input.value = a.artist
                        break

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle 'Various Artists' checkbox changes."""
        if event.checkbox.id == "va_checkbox":
            album_artist_input = self.query_one("#album_artist", Input)
            if event.value:
                album_artist_input.value = VARIOUS_ARTISTS
                album_artist_input.disabled = True
            else:
                album_artist_input.disabled = False
                current_artist = self.query_one("#artist", Input).value or ""
                album_artist_input.value = current_artist

    def on_mount(self) -> None:
        """Initialize visibility based on default selection."""
        album_select = self.query_one("#album_select", Select)
        album_name_input = self.query_one("#album_name", Input)
        album_artist_input = self.query_one("#album_artist", Input)
        va_checkbox = self.query_one("#va_checkbox", Checkbox)

        if (album_select.value or "") == "__create__":
            album_name_input.display = True
            album_artist_input.display = True
            va_checkbox.display = True
        else:
            album_name_input.display = False
            album_artist_input.display = False
            va_checkbox.display = False


async def confirm_metadata(initial: TrackMetadata) -> TrackMetadata:
    """Display TUI for reviewing and confirming metadata.

    Args:
        initial: Initial metadata from AI inference.

    Returns:
        Confirmed/edited metadata from user.
    """
    app = ConfirmMetadataApp(initial)
    result = await app.run_async()
    return result

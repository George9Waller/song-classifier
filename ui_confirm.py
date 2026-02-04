from typing import Optional, List

from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Label, Select, Checkbox
from textual.containers import Vertical

from models import AlbumMetadata, TrackMetadata
from data import get_album_metadata


GENRE_OPTIONS: List[str] = [
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


class ConfirmMetadataApp(App[TrackMetadata]):
    CSS = """
    Screen { align: center middle; }
    #form { width: 80; }
    Input, Select { margin: 1 0; }
    Button { margin-top: 1; }
    """

    def __init__(self, initial: TrackMetadata) -> None:
        super().__init__()
        self.initial = initial
        self._result: Optional[TrackMetadata] = None

    def compose(self) -> ComposeResult:
        genre_options = list(GENRE_OPTIONS)
        if self.initial.genre and self.initial.genre not in genre_options:
            genre_options.insert(0, self.initial.genre)

        albums = get_album_metadata()
        # Use (label, value) ordering as expected by Textual Select
        album_options = [(f"{a.name} ({a.artist})", a.name) for a in albums]
        # Always include create option in the list to simplify default handling
        album_options = album_options + [("Create new...", "__create__")]
        # If initial album exists but isn't in options yet, insert it at the top
        if (
            self.initial.album
            and self.initial.album.name
            and self.initial.album.name not in [v for _, v in album_options]
        ):
            initial_label = (
                f"{self.initial.album.name} ({self.initial.album.artist})"
                if self.initial.album.artist
                else self.initial.album.name
            )
            album_options.insert(0, (initial_label, self.initial.album.name))

        # Work out a safe default value for the album select
        desired_default_album = (
            self.initial.album.name
            if (self.initial.album and self.initial.album.name)
            else None
        )
        option_ids = [v for _, v in album_options]
        if desired_default_album and desired_default_album not in option_ids:
            # If we have an initial album name but it wasn't in options (should have been inserted above),
            # insert it now as a safety net.
            initial_label = (
                f"{self.initial.album.name} ({self.initial.album.artist})"
                if self.initial.album and self.initial.album.artist
                else self.initial.album.name
            )
            album_options.insert(0, (initial_label, self.initial.album.name))
            option_ids.insert(0, self.initial.album.name)

        # Final default: use initial if present and valid; else first available; else "__create__"
        default_album_value = (
            desired_default_album
            if (desired_default_album and desired_default_album in option_ids)
            else (option_ids[0] if option_ids else "__create__")
        )

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
            Checkbox("Various Artists", id="va_checkbox"),
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
        if event.button.id == "confirm":
            track = self.query_one("#track", Input).value or ""
            artist = self.query_one("#artist", Input).value or ""
            album_select = self.query_one("#album_select", Select)
            selected_album = album_select.value or ""
            if selected_album == "__create__":
                album_name = self.query_one("#album_name", Input).value or ""
                va_checked = self.query_one("#va_checkbox", Checkbox).value
                if va_checked:
                    album_artist = "Various Artists"
                else:
                    album_artist = (
                        self.query_one("#album_artist", Input).value or artist
                    )
            else:
                album_name = selected_album
                # derive album artist from known albums
                album_artist = (
                    getattr(get_album_metadata(key=selected_album), "artist", None)
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
        if event.select.id == "album_select":
            value = event.value or ""
            album_name_input = self.query_one("#album_name", Input)
            album_artist_input = self.query_one("#album_artist", Input)
            va_checkbox = self.query_one("#va_checkbox", Checkbox)
            if value == "__create__":
                # Show new album input and let user type; default album artist to artist field
                album_name_input.display = True
                album_artist_input.display = True
                va_checkbox.display = True
                current_artist = self.query_one("#artist", Input).value or ""
                album_artist_input.value = current_artist
                va_checkbox.value = current_artist.strip().lower() == "various artists"
                album_artist_input.disabled = va_checkbox.value
            else:
                # Hide new album name input and set album artist from known selection if available
                album_name_input.display = False
                album_artist_input.display = False
                va_checkbox.display = False
                va_checkbox.value = False
                album_artist_input.disabled = False
                # Try to set album artist from known albums list
                for a in get_album_metadata():
                    if a.name == value:
                        album_artist_input.value = a.artist
                        break

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "va_checkbox":
            album_artist_input = self.query_one("#album_artist", Input)
            if event.value:
                album_artist_input.value = "Various Artists"
                album_artist_input.disabled = True
            else:
                # Re-enable and default back to current track artist
                album_artist_input.disabled = False
                current_artist = self.query_one("#artist", Input).value or ""
                album_artist_input.value = current_artist

    def on_mount(self) -> None:
        # Initialize visibility based on default selection
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


def confirm_metadata(initial: TrackMetadata) -> TrackMetadata:
    app = ConfirmMetadataApp(initial)
    return app.run()

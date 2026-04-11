"""Music Library Editor — interactive multi-screen Textual TUI."""

from __future__ import annotations

import hashlib

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from src.data import (
    get_file_metadata,
    upsert_album_metadata,
    upsert_track_metadata,
)
from src.data.models import AlbumMetadata, TrackMetadata

# Palette used to colour artist/genre cards deterministically.
_PALETTE = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#e91e63",
    "#00bcd4", "#8bc34a", "#ff5722", "#607d8b",
]


def _color(name: str) -> str:
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(_PALETTE)
    return _PALETTE[idx]


def _sort_key(track: TrackMetadata, col: str) -> str:
    if col == "album":
        return (track.album.name or "").lower()
    return str(getattr(track, col, "") or "").lower()


# ──────────────────────────── clickable table ──────────────────────────────

class ClickableTable(DataTable):
    """DataTable with cursor_type='row' that fires RowClicked on single click or Enter.

    Textual's DataTable defaults to cursor_type='cell', which means RowSelected and
    RowHighlighted are never posted.  This subclass:
      - defaults to cursor_type='row'
      - posts ClickableTable.RowClicked on mouse click (any row, first or subsequent)
      - overrides action_select_cursor so Enter also posts RowClicked
    This lets callers use a single handler (on_clickable_table_row_clicked) for both
    mouse and keyboard activation without any flag-based hacks.
    """

    class RowClicked(Message):
        """Posted when the user clicks a data row or presses Enter."""

        def __init__(self, data_table: DataTable, row_key: str) -> None:
            self.data_table = data_table
            self.row_key = row_key
            super().__init__()

        @property
        def control(self) -> DataTable:
            return self.data_table

    def _emit_row_clicked(self) -> None:
        if self.row_count == 0:
            return
        try:
            row = self.ordered_rows[self.cursor_row]
            self.post_message(self.RowClicked(self, str(row.key)))
        except Exception:
            pass

    def on_click(self, event) -> None:
        """Fire RowClicked on mouse click on a data row (not the header)."""
        meta = event.style.meta
        if "row" not in meta or meta.get("row", -1) < 0:
            return  # header click or padding — ignore
        self._emit_row_clicked()

    def action_select_cursor(self) -> None:
        """Fire RowClicked on Enter (instead of the default CellSelected/RowSelected)."""
        self._emit_row_clicked()


# ──────────────────────────── cards ────────────────────────────────────────

class ArtistCard(Static):
    """Coloured initial + name card for an artist."""

    def __init__(self, artist: str, **kwargs) -> None:
        super().__init__(classes="card card--artist", **kwargs)
        self._artist = artist

    def compose(self) -> ComposeResult:
        initial = (self._artist or "?")[0].upper()
        yield Static(initial, classes="card-avatar")
        yield Label(self._artist, classes="card-name")

    def on_mount(self) -> None:
        self.query_one(".card-avatar", Static).styles.background = _color(self._artist)

    def on_click(self) -> None:
        self.app.push_screen(ArtistDetailScreen(self._artist))


class AlbumCard(Static):
    """Name + artist card for an album."""

    def __init__(self, album_name: str, album_artist: str, **kwargs) -> None:
        super().__init__(classes="card card--album", **kwargs)
        self._album_name = album_name
        self._album_artist = album_artist

    def compose(self) -> ComposeResult:
        yield Label(self._album_name, classes="card-name")
        yield Label(self._album_artist, classes="card-subtitle")

    def on_click(self) -> None:
        self.app.push_screen(FilteredTracksScreen("album", self._album_name))


class GenreCard(Static):
    """Tinted card for a genre."""

    def __init__(self, genre: str, **kwargs) -> None:
        super().__init__(classes="card card--genre", **kwargs)
        self._genre = genre

    def compose(self) -> ComposeResult:
        yield Label(self._genre, classes="card-name")

    def on_mount(self) -> None:
        self.styles.background = _color(self._genre)

    def on_click(self) -> None:
        self.app.push_screen(FilteredTracksScreen("genre", self._genre))


# ──────────────────────────── search result items ──────────────────────────

class _TrackResult(Static):
    def __init__(self, track: TrackMetadata) -> None:
        super().__init__(
            f"  \u266a  {track.track}  \u2014  {track.artist}",
            classes="search-result-item",
        )
        self._track = track

    def on_click(self) -> None:
        self.app.push_screen(TrackEditModal(self._track))


class _ArtistResult(Static):
    def __init__(self, artist: str) -> None:
        super().__init__(f"  \u25cf  {artist}", classes="search-result-item")
        self._artist = artist

    def on_click(self) -> None:
        self.app.push_screen(ArtistDetailScreen(self._artist))


class _GenreResult(Static):
    def __init__(self, genre: str) -> None:
        super().__init__(f"  \u266c  {genre}", classes="search-result-item")
        self._genre = genre

    def on_click(self) -> None:
        self.app.push_screen(FilteredTracksScreen("genre", self._genre))


# ──────────────────────────── search panel ─────────────────────────────────

class SearchResultsPanel(Container):
    """Live search overlay shown beneath the search input."""

    def compose(self) -> ComposeResult:
        yield Label("Tracks", classes="search-section-title")
        yield Container(id="sr-tracks")
        yield Label("Artists", classes="search-section-title")
        yield Container(id="sr-artists")
        yield Label("Genres", classes="search-section-title")
        yield Container(id="sr-genres")

    def update_results(self, query: str) -> None:
        tracks: list[TrackMetadata] = get_file_metadata() or []  # type: ignore[assignment]
        q = query.lower()

        matched_tracks = [
            t for t in tracks
            if q in (t.track or "").lower()
            or q in (t.artist or "").lower()
            or q in (t.album.name or "").lower()
            or q in (t.genre or "").lower()
        ][:5]
        matched_artists = sorted({t.artist for t in tracks if q in (t.artist or "").lower()})[:5]
        matched_genres = sorted({t.genre for t in tracks if q in (t.genre or "").lower()})[:5]

        c_tracks = self.query_one("#sr-tracks", Container)
        c_tracks.remove_children()
        for t in matched_tracks:
            c_tracks.mount(_TrackResult(t))

        c_artists = self.query_one("#sr-artists", Container)
        c_artists.remove_children()
        for a in matched_artists:
            c_artists.mount(_ArtistResult(a))

        c_genres = self.query_one("#sr-genres", Container)
        c_genres.remove_children()
        for g in matched_genres:
            c_genres.mount(_GenreResult(g))

        self.display = bool(matched_tracks or matched_artists or matched_genres)


# ──────────────────────────── edit modal ───────────────────────────────────

class TrackEditModal(ModalScreen[bool]):
    """Centre-screen modal for editing a single track's metadata."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, track: TrackMetadata, **kwargs) -> None:
        super().__init__(**kwargs)
        self._track = track

    def compose(self) -> ComposeResult:
        with Container(classes="edit-modal"):
            yield Label("Edit Track", classes="modal-title")
            yield Label("Track title")
            yield Input(value=self._track.track or "", id="inp-track")
            yield Label("Artist")
            yield Input(value=self._track.artist or "", id="inp-artist")
            yield Label("Album")
            yield Input(value=self._track.album.name or "", id="inp-album")
            yield Label("Album Artist")
            yield Input(value=self._track.album.artist or "", id="inp-album-artist")
            yield Label("Genre")
            yield Input(value=self._track.genre or "", id="inp-genre")
            yield Label("Date")
            yield Input(value=self._track.date or "", id="inp-date")
            with Horizontal(classes="modal-buttons"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", id="btn-cancel")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(False)
        elif event.button.id == "btn-save":
            self._save()

    def _save(self) -> None:
        album = AlbumMetadata(
            name=self.query_one("#inp-album", Input).value,
            artist=self.query_one("#inp-album-artist", Input).value,
        )
        updated = TrackMetadata(
            key=self._track.key,
            track=self.query_one("#inp-track", Input).value,
            artist=self.query_one("#inp-artist", Input).value,
            album=album,
            genre=self.query_one("#inp-genre", Input).value,
            date=self.query_one("#inp-date", Input).value or None,
        )
        upsert_track_metadata(updated)
        upsert_album_metadata(album)
        self.dismiss(True)


# ──────────────────────────── grid pane helpers ─────────────────────────────

def _build_grid(cards: list) -> Container:
    """Wrap a list of card widgets in a grid container."""
    return Container(*cards, classes="card-grid")


def _sort_bar(*labels: str) -> Horizontal:
    return Horizontal(
        Label("Sort:"),
        *[Button(lbl, compact=True, classes="sort-btn") for lbl in labels],
        classes="sort-bar",
    )


# ──────────────────────────── artists pane ─────────────────────────────────

class ArtistsPane(Container):
    def compose(self) -> ComposeResult:
        yield _sort_bar("A-Z", "Z-A")
        yield ScrollableContainer(Container(id="artists-grid"))

    def on_mount(self) -> None:
        self._populate(reverse=False)

    def _populate(self, reverse: bool) -> None:
        tracks: list[TrackMetadata] = get_file_metadata() or []  # type: ignore[assignment]
        artists = sorted({t.artist for t in tracks if t.artist}, reverse=reverse)
        grid_container = self.query_one("#artists-grid", Container)
        grid_container.remove_children()
        grid_container.mount(_build_grid([ArtistCard(a) for a in artists]))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        lbl = str(event.button.label)
        if lbl == "A-Z":
            self._populate(reverse=False)
        elif lbl == "Z-A":
            self._populate(reverse=True)
        event.stop()


# ──────────────────────────── albums pane ──────────────────────────────────

class AlbumsPane(Container):
    def compose(self) -> ComposeResult:
        yield _sort_bar("A-Z", "Z-A", "By Artist")
        yield ScrollableContainer(Container(id="albums-grid"))

    def on_mount(self) -> None:
        self._populate(sort_by="name", reverse=False)

    def _populate(self, sort_by: str = "name", reverse: bool = False) -> None:
        tracks: list[TrackMetadata] = get_file_metadata() or []  # type: ignore[assignment]
        seen: set[str] = set()
        albums: list[tuple[str, str]] = []
        for t in tracks:
            if t.album.name not in seen:
                seen.add(t.album.name)
                albums.append((t.album.name, t.album.artist))

        if sort_by == "name":
            albums.sort(key=lambda a: a[0].lower(), reverse=reverse)
        else:
            albums.sort(key=lambda a: a[1].lower())

        grid_container = self.query_one("#albums-grid", Container)
        grid_container.remove_children()
        grid_container.mount(_build_grid([AlbumCard(name, artist) for name, artist in albums]))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        lbl = str(event.button.label)
        if lbl == "A-Z":
            self._populate(sort_by="name", reverse=False)
        elif lbl == "Z-A":
            self._populate(sort_by="name", reverse=True)
        elif lbl == "By Artist":
            self._populate(sort_by="artist")
        event.stop()


# ──────────────────────────── genres pane ──────────────────────────────────

class GenresPane(Container):
    def compose(self) -> ComposeResult:
        yield _sort_bar("A-Z", "Z-A")
        yield ScrollableContainer(Container(id="genres-grid"))

    def on_mount(self) -> None:
        self._populate(reverse=False)

    def _populate(self, reverse: bool) -> None:
        tracks: list[TrackMetadata] = get_file_metadata() or []  # type: ignore[assignment]
        genres = sorted({t.genre for t in tracks if t.genre}, reverse=reverse)
        grid_container = self.query_one("#genres-grid", Container)
        grid_container.remove_children()
        grid_container.mount(_build_grid([GenreCard(g) for g in genres]))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        lbl = str(event.button.label)
        if lbl == "A-Z":
            self._populate(reverse=False)
        elif lbl == "Z-A":
            self._populate(reverse=True)
        event.stop()


# ──────────────────────────── tracks helpers ───────────────────────────────

def _add_track_columns(table: DataTable) -> None:
    table.add_column("Track", key="track")
    table.add_column("Album", key="album")
    table.add_column("Artist", key="artist")
    table.add_column("Genre", key="genre")
    table.add_column("Date", key="date")


def _fill_tracks(table: DataTable, tracks: list[TrackMetadata], sort_col: str, reverse: bool) -> None:
    table.clear()
    sorted_tracks = sorted(tracks, key=lambda t: _sort_key(t, sort_col), reverse=reverse)
    for t in sorted_tracks:
        table.add_row(
            t.track or "",
            t.album.name or "",
            t.artist or "",
            t.genre or "",
            t.date or "",
            key=t.key,
        )


def _track_by_key(key: str) -> TrackMetadata | None:
    tracks: list[TrackMetadata] = get_file_metadata() or []  # type: ignore[assignment]
    return next((t for t in tracks if t.key == key), None)


# ──────────────────────────── filtered tracks screen ───────────────────────

class FilteredTracksScreen(Screen):
    """Shows tracks filtered by album or genre."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, filter_type: str, value: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._filter_type = filter_type
        self._value = value
        self._sort_col = "track"
        self._sort_reverse = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(classes="detail-header"):
            yield Button("Back", id="btn-back")
            label = "Album" if self._filter_type == "album" else "Genre"
            yield Label(f"{label}: {self._value}", classes="detail-title")
        yield ScrollableContainer(
            ClickableTable(zebra_stripes=True, cursor_type="row", id="filtered-table")
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#filtered-table", ClickableTable)
        _add_track_columns(table)
        self._refresh()

    def _refresh(self) -> None:
        tracks: list[TrackMetadata] = get_file_metadata() or []  # type: ignore[assignment]
        if self._filter_type == "album":
            filtered = [t for t in tracks if t.album.name == self._value]
        else:
            filtered = [t for t in tracks if t.genre == self._value]
        _fill_tracks(
            self.query_one("#filtered-table", ClickableTable),
            filtered,
            self._sort_col,
            self._sort_reverse,
        )

    def on_screen_resume(self) -> None:
        self._refresh()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col = str(event.column_key)
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._refresh()

    def on_clickable_table_row_clicked(self, event: ClickableTable.RowClicked) -> None:
        track = _track_by_key(event.row_key)
        if track:
            self.app.push_screen(TrackEditModal(track))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()


# ──────────────────────────── artist detail screen ─────────────────────────

class ArtistDetailScreen(Screen):
    """Shows albums and tracks for a single artist."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, artist: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._artist = artist
        self._sort_col = "track"
        self._sort_reverse = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(classes="detail-header"):
            yield Button("Back", id="btn-back")
            yield Label(f"Artist: {self._artist}", classes="detail-title")
        yield ScrollableContainer(
            Label("Albums", classes="section-title"),
            Container(id="artist-albums"),
            Label("Tracks", classes="section-title"),
            ClickableTable(zebra_stripes=True, cursor_type="row", id="artist-tracks"),
            id="artist-detail-scroll",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#artist-tracks", ClickableTable)
        _add_track_columns(table)
        self._refresh()

    def _refresh(self) -> None:
        tracks: list[TrackMetadata] = get_file_metadata() or []  # type: ignore[assignment]
        artist_tracks = [t for t in tracks if t.artist == self._artist]

        albums: list[tuple[str, str]] = []
        seen: set[str] = set()
        for t in artist_tracks:
            if t.album.name not in seen:
                seen.add(t.album.name)
                albums.append((t.album.name, t.album.artist))
        albums.sort(key=lambda a: a[0].lower())

        albums_container = self.query_one("#artist-albums", Container)
        albums_container.remove_children()
        albums_container.mount(_build_grid([AlbumCard(n, a) for n, a in albums]))

        _fill_tracks(
            self.query_one("#artist-tracks", ClickableTable),
            artist_tracks,
            self._sort_col,
            self._sort_reverse,
        )

    def on_screen_resume(self) -> None:
        self._refresh()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col = str(event.column_key)
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._refresh()

    def on_clickable_table_row_clicked(self, event: ClickableTable.RowClicked) -> None:
        track = _track_by_key(event.row_key)
        if track:
            self.app.push_screen(TrackEditModal(track))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()


# ──────────────────────────── main screen ──────────────────────────────────

class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="search-container"):
            yield Input(placeholder="Search tracks, artists, genres...", id="search-input")
            yield SearchResultsPanel(id="search-results")
        with TabbedContent(id="main-tabs"):
            with TabPane("Tracks", id="tab-tracks"):
                yield ScrollableContainer(
                    ClickableTable(zebra_stripes=True, cursor_type="row", id="tracks-table"),
                )
            with TabPane("Albums", id="tab-albums"):
                yield AlbumsPane(id="albums-pane")
            with TabPane("Artists", id="tab-artists"):
                yield ArtistsPane(id="artists-pane")
            with TabPane("Genres", id="tab-genres"):
                yield GenresPane(id="genres-pane")
        yield Footer()

    def on_mount(self) -> None:
        self._sort_col = "track"
        self._sort_reverse = False
        table = self.query_one("#tracks-table", ClickableTable)
        _add_track_columns(table)
        self._populate_tracks()
        self.query_one("#search-results", SearchResultsPanel).display = False

    def _populate_tracks(self) -> None:
        tracks: list[TrackMetadata] = get_file_metadata() or []  # type: ignore[assignment]
        _fill_tracks(
            self.query_one("#tracks-table", ClickableTable),
            tracks,
            self._sort_col,
            self._sort_reverse,
        )

    def on_screen_resume(self) -> None:
        self._populate_tracks()

    # ── search ──────────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search-input":
            return
        q = event.value.strip()
        panel = self.query_one("#search-results", SearchResultsPanel)
        if len(q) >= 2:
            panel.update_results(q)
        else:
            panel.display = False

    # ── tracks table ────────────────────────────────────────────────────────

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        if event.data_table.id != "tracks-table":
            return
        col = str(event.column_key)
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._populate_tracks()

    def on_clickable_table_row_clicked(self, event: ClickableTable.RowClicked) -> None:
        if event.data_table.id != "tracks-table":
            return
        track = _track_by_key(event.row_key)
        if track:
            self.app.push_screen(TrackEditModal(track))


# ──────────────────────────── app ──────────────────────────────────────────

class Editor(App):
    CSS_PATH = "editor.tcss"
    TITLE = "Music Library"
    SUB_TITLE = "Browse your collection"

    BINDINGS = [Binding("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(MainScreen())


if __name__ == "__main__":
    Editor().run()

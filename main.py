import os
from ai_metadata import parse_metadata_with_ai
from data import get_file_metadata
from file_metadata import read_file_metadata, write_file_metadata, is_already_processed
from file_transport import FileTransport, TransportType
from ui_confirm import confirm_metadata
from data import upsert_album_metadata, upsert_track_metadata

PATH = "sets"


def classify_filename(
    filename,
    base_path,
    file_transport: FileTransport,
    skip_processed_files=True,
    skip_files_in_metadata=False,
):
    print(f"-- {filename} --")
    if skip_files_in_metadata and get_file_metadata(key=filename):
        print("File already in metadata, SKIPPING\n")
        return

    # Ensure temp local copy
    print("1. Loading file locally")
    local_path = file_transport.load_file(filename, base_path)

    # Read any existing tags from the downloaded file
    print("2. Reading existing metadata")
    existing = read_file_metadata(local_path)

    # If already processed, skip and delete temp
    if skip_processed_files and is_already_processed(local_path):
        print("File already processed, SKIPPING\n")
        try:
            os.remove(local_path)
        except Exception:
            pass
        return

    # AI parse using filename; UI confirm
    print("3. Estimating metadata with AI")
    ai_metadata = parse_metadata_with_ai(filename, existing)
    confirmed = confirm_metadata(ai_metadata)

    # Upsert album and track CSV metadata
    print("4. Inserting metadata in CSVs")
    upsert_album_metadata(confirmed.album)
    upsert_track_metadata(confirmed)

    # Write the confirmed tags back into the local file
    print("5. Updating the file metadata")
    write_file_metadata(local_path, confirmed)

    # Upload and replace original on WebDAV
    print("6. Replacing file on server\n")
    file_transport.save_file(local_path, base_path, filename)

    # Clean up local temp file
    if file_transport.cleanup_local_files:
        try:
            os.remove(local_path)
        except Exception:
            pass


if __name__ == "__main__":
    # filename = "AUCKLAND_NEW_ZEALAND_2025_FULL_LIVE_SET.mp3"
    # classify_filename(filename)

    use_webdav = input("Use webdav for remote metadata editing? [Y/n]") == "Y"
    transport_type = TransportType.WEBDAV if use_webdav else TransportType.LOCAL

    file_transport = FileTransport(transport_type)

    for filename in file_transport.list_files(PATH):
        classify_filename(
            filename,
            PATH,
            file_transport=file_transport,
            skip_processed_files=True,
            skip_files_in_metadata=True,
        )

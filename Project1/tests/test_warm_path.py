"""Task 5: a warm instance skips reprocessing while the CSV's ETag is unchanged."""
from unittest.mock import MagicMock

from lambda_function import process_nutritional_data_from_azurite

CSV = (b"Diet_type,Recipe_name,Cuisine_type,Protein(g),Carbs(g),Fat(g)\n"
       b"keto,A,italian,10,5,2\n")


def blob_service(etag):
    service = MagicMock()
    blob = service.get_blob_client.return_value
    blob.get_blob_properties.return_value.etag = etag
    blob.download_blob.return_value.properties.etag = etag
    blob.download_blob.return_value.readall.return_value = CSV
    return service, blob


def test_unchanged_csv_is_not_downloaded_again(tmp_path):
    service, blob = blob_service('"0x1"')
    path = tmp_path / "results.json"
    first = process_nutritional_data_from_azurite(path, service)
    second = process_nutritional_data_from_azurite(path, service)
    assert second == first
    assert blob.download_blob.call_count == 1


def test_changed_csv_is_processed_again(tmp_path):
    service, blob = blob_service('"0x1"')
    path = tmp_path / "results.json"
    process_nutritional_data_from_azurite(path, service)
    blob.get_blob_properties.return_value.etag = '"0x2"'
    blob.download_blob.return_value.properties.etag = '"0x2"'
    process_nutritional_data_from_azurite(path, service)
    assert blob.download_blob.call_count == 2


def test_deleted_results_file_is_rebuilt(tmp_path):
    service, blob = blob_service('"0x1"')
    path = tmp_path / "results.json"
    process_nutritional_data_from_azurite(path, service)
    path.unlink()
    process_nutritional_data_from_azurite(path, service)
    assert path.exists()
    assert blob.download_blob.call_count == 2

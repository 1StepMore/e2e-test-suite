"""Cloud storage E2E tests for Omni_Suite.

Tests S3 and Azure Blob upload/download operations with mocking support.

NOTE: This file tests ``opp.cloud_utils`` which has been removed/refactored
to ORF's ``orf.cloud`` module. The import will fail at module load.
ORF cloud client tests live in ``Omni_Re_Formatter/tests/test_cloud_clients.py``.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from conftest import setup_component_paths
setup_component_paths()

pytest.skip("opp.cloud_utils module was removed; cloud tests migrated to "
            "Omni_Re_Formatter/tests/test_cloud_clients.py",
            allow_module_level=True)


# =============================================================================
# Markers
# =============================================================================

pytestmark = [
    pytest.mark.requires_opp,
    pytest.mark.requires_orf,
]


# =============================================================================
# Credential Detection
# =============================================================================

def _check_aws_credentials() -> bool:
    """Check if AWS credentials are available."""
    return (
        os.environ.get("AWS_ACCESS_KEY_ID") is not None
        and os.environ.get("AWS_SECRET_ACCESS_KEY") is not None
    ) or os.environ.get("AWS_PROFILE") is not None


def _check_azure_credentials() -> bool:
    """Check if Azure credentials are available."""
    return (
        os.environ.get("AZURE_STORAGE_CONNECTION_STRING") is not None
        or (
            os.environ.get("AZURE_STORAGE_ACCOUNT") is not None
            and os.environ.get("AZURE_STORAGE_KEY") is not None
        )
    )


# =============================================================================
# S3 Tests
# =============================================================================

class TestS3Operations:
    """Tests for AWS S3 storage operations."""

    @pytest.fixture
    def s3_bucket_name(self) -> str:
        """Get S3 bucket name from environment or use default."""
        return os.environ.get("S3_BUCKET_NAME", "omni-suite-test-bucket")

    @pytest.fixture
    def s3_object_key(self) -> str:
        """Get S3 object key prefix."""
        return "test_uploads/omni_suite"

    @pytest.fixture
    def sample_docx_path(self, tmp_path: Path) -> Path:
        """Create a sample DOCX for upload testing."""
        from docx import Document

        doc = Document()
        doc.add_heading("Cloud Upload Test Document", level=1)
        doc.add_paragraph("This document is for testing S3 upload functionality.")
        doc.add_paragraph("It contains multiple paragraphs to simulate a real document.")

        output_path = tmp_path / "cloud_test_doc.docx"
        doc.save(str(output_path))
        return output_path

    def test_s3_upload_with_mock(self, sample_docx_path, s3_bucket_name, s3_object_key):
        """Test S3 upload operation with mocked boto3.

        This test verifies the upload flow without requiring real AWS credentials.
        """
        mock_s3_client = MagicMock()
        mock_s3_client.upload_file.return_value = None

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value = mock_s3_client

            from opp.cloud_utils import upload_to_s3

            result = upload_to_s3(
                file_path=sample_docx_path,
                bucket=s3_bucket_name,
                object_key=f"{s3_object_key}/test_doc.docx"
            )

            assert result is True
            mock_s3_client.upload_file.assert_called_once()

        print(f"\n✓ S3 upload (mocked) completed for {sample_docx_path.name}")

    def test_s3_download_with_mock(self, tmp_path: Path, s3_bucket_name, s3_object_key):
        """Test S3 download operation with mocked boto3."""
        mock_s3_client = MagicMock()

        # Create a sample file to simulate download
        sample_content = b"Mock PDF content for download testing"
        mock_s3_client.download_fileobj.return_value = None

        output_path = tmp_path / "downloaded_doc.pdf"

        def mock_download(Bucket, Key, Fileobj):
            Fileobj.write(sample_content)

        mock_s3_client.download_fileobj.side_effect = mock_download

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value = mock_s3_client

            from opp.cloud_utils import download_from_s3

            result = download_from_s3(
                bucket=s3_bucket_name,
                object_key=f"{s3_object_key}/test_doc.pdf",
                output_path=output_path
            )

            assert result is True
            assert output_path.exists()
            assert output_path.read_bytes() == sample_content

        print(f"\n✓ S3 download (mocked) completed")

    @pytest.mark.requires_opp
    def test_s3_upload_real_if_credentials(self, sample_docx_path, s3_bucket_name, s3_object_key):
        """Test real S3 upload if credentials are available.

        This test only runs if AWS credentials are properly configured.
        """
        if not _check_aws_credentials():
            pytest.skip("AWS credentials not available")

        import boto3
        from opp.cloud_utils import upload_to_s3

        s3_client = boto3.client("s3")

        result = upload_to_s3(
            file_path=sample_docx_path,
            bucket=s3_bucket_name,
            object_key=f"{s3_object_key}/test_doc_real.docx"
        )

        assert result is True
        print(f"\n✓ S3 upload (real) completed for {sample_docx_path.name}")

    def test_s3_presigned_url_generation(self, s3_bucket_name, s3_object_key):
        """Test S3 presigned URL generation."""
        mock_s3_client = MagicMock()
        mock_s3_client.generate_presigned_url.return_value = (
            f"https://{s3_bucket_name}.s3.amazonaws.com/{s3_object_key}/test.txt"
            f"?Signature=mock&Expires=1234567890"
        )

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value = mock_s3_client

            from opp.cloud_utils import generate_presigned_url

            url = generate_presigned_url(
                bucket=s3_bucket_name,
                object_key=f"{s3_object_key}/test.txt",
                expiration=3600
            )

            assert url is not None
            assert "s3.amazonaws.com" in url

        print(f"\n✓ S3 presigned URL generated")

    def test_s3_batch_upload(self, tmp_path: Path, s3_bucket_name, s3_object_key):
        """Test batch upload of multiple files to S3."""
        # Create multiple test files
        test_files = []
        for i in range(3):
            file_path = tmp_path / f"batch_test_{i}.txt"
            file_path.write_text(f"Content of batch test file {i}")
            test_files.append(file_path)

        mock_s3_client = MagicMock()
        mock_s3_client.upload_file.return_value = None

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value = mock_s3_client

            from opp.cloud_utils import upload_batch_to_s3

            results = upload_batch_to_s3(
                file_paths=test_files,
                bucket=s3_bucket_name,
                object_prefix=s3_object_key
            )

            assert len(results) == len(test_files)
            assert all(r is True for r in results)

        print(f"\n✓ S3 batch upload of {len(test_files)} files (mocked) completed")


# =============================================================================
# Azure Blob Tests
# =============================================================================

class TestAzureBlobOperations:
    """Tests for Azure Blob storage operations."""

    @pytest.fixture
    def azure_container_name(self) -> str:
        """Get Azure container name from environment or use default."""
        return os.environ.get("AZURE_CONTAINER_NAME", "omni-suite-test")

    @pytest.fixture
    def azure_blob_name(self) -> str:
        """Get Azure blob name prefix."""
        return "test_uploads/omni_suite"

    @pytest.fixture
    def sample_docx_path(self, tmp_path: Path) -> Path:
        """Create a sample DOCX for upload testing."""
        from docx import Document

        doc = Document()
        doc.add_heading("Azure Upload Test Document", level=1)
        doc.add_paragraph("This document is for testing Azure Blob upload functionality.")

        output_path = tmp_path / "azure_test_doc.docx"
        doc.save(str(output_path))
        return output_path

    def test_azure_blob_upload_with_mock(self, sample_docx_path, azure_container_name, azure_blob_name):
        """Test Azure Blob upload operation with mocked SDK.

        This test verifies the upload flow without requiring real Azure credentials.
        """
        mock_blob_service_client = MagicMock()
        mock_container_client = MagicMock()
        mock_blob_client = MagicMock()

        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.upload_blob.return_value = MagicMock()

        with patch("azure.storage.blob.BlobServiceClient") as mock_blob_service:
            mock_blob_service.from_connection_string.return_value = mock_blob_service_client

            from opp.cloud_utils import upload_to_azure

            result = upload_to_azure(
                file_path=sample_docx_path,
                container_name=azure_container_name,
                blob_name=f"{azure_blob_name}/test_doc.docx"
            )

            assert result is True
            mock_blob_client.upload_blob.assert_called_once()

        print(f"\n✓ Azure Blob upload (mocked) completed for {sample_docx_path.name}")

    def test_azure_blob_download_with_mock(self, tmp_path: Path, azure_container_name, azure_blob_name):
        """Test Azure Blob download operation with mocked SDK."""
        sample_content = b"Mock PDF content for Azure download testing"

        mock_blob_service_client = MagicMock()
        mock_container_client = MagicMock()
        mock_blob_client = MagicMock()

        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client

        # Mock download
        mock_blob_client.download_blob.return_value.readall.return_value = sample_content

        output_path = tmp_path / "azure_downloaded.pdf"

        with patch("azure.storage.blob.BlobServiceClient") as mock_blob_service:
            mock_blob_service.from_connection_string.return_value = mock_blob_service_client

            from opp.cloud_utils import download_from_azure

            result = download_from_azure(
                container_name=azure_container_name,
                blob_name=f"{azure_blob_name}/test_doc.pdf",
                output_path=output_path
            )

            assert result is True
            assert output_path.exists()
            assert output_path.read_bytes() == sample_content

        print(f"\n✓ Azure Blob download (mocked) completed")

    @pytest.mark.requires_azure
    def test_azure_blob_upload_real_if_credentials(self, sample_docx_path, azure_container_name, azure_blob_name):
        """Test real Azure Blob upload if credentials are available.

        This test only runs if Azure credentials are properly configured.
        """
        if not _check_azure_credentials():
            pytest.skip("Azure credentials not available")

        from opp.cloud_utils import upload_to_azure

        result = upload_to_azure(
            file_path=sample_docx_path,
            container_name=azure_container_name,
            blob_name=f"{azure_blob_name}/test_doc_real.docx"
        )

        assert result is True
        print(f"\n✓ Azure Blob upload (real) completed for {sample_docx_path.name}")

    def test_azure_blob_sas_token_generation(self, azure_container_name, azure_blob_name):
        """Test Azure Blob SAS token generation."""
        mock_blob_service_client = MagicMock()

        # Mock generate_blob_sas
        mock_blob_service_client.get_blob_sas_client.return_value = MagicMock()
        mock_blob_service_client.get_blob_sas_client.return_value.generate_token.return_value = (
            "sv=2021-06-08&ss=b&srt=co&sp=rwdlacu&se=2026-01-01T00:00:00Z&st=2026-01-01T00:00:00Z&spr=https&sig=mock_signature"
        )

        with patch("azure.storage.blob.BlobServiceClient") as mock_blob_service:
            mock_blob_service.from_connection_string.return_value = mock_blob_service_client

            from opp.cloud_utils import generate_azure_sas_token

            token = generate_azure_sas_token(
                container_name=azure_container_name,
                blob_name=f"{azure_blob_name}/test.txt",
                expiration=3600
            )

            assert token is not None

        print(f"\n✓ Azure Blob SAS token generated")

    def test_azure_blob_batch_upload(self, tmp_path: Path, azure_container_name, azure_blob_name):
        """Test batch upload of multiple files to Azure Blob."""
        # Create multiple test files
        test_files = []
        for i in range(3):
            file_path = tmp_path / f"azure_batch_test_{i}.txt"
            file_path.write_text(f"Content of Azure batch test file {i}")
            test_files.append(file_path)

        mock_blob_service_client = MagicMock()
        mock_container_client = MagicMock()
        mock_blob_client = MagicMock()

        mock_blob_service_client.get_container_client.return_value = mock_container_client
        mock_container_client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.upload_blob.return_value = MagicMock()

        with patch("azure.storage.blob.BlobServiceClient") as mock_blob_service:
            mock_blob_service.from_connection_string.return_value = mock_blob_service_client

            from opp.cloud_utils import upload_batch_to_azure

            results = upload_batch_to_azure(
                file_paths=test_files,
                container_name=azure_container_name,
                blob_prefix=azure_blob_name
            )

            assert len(results) == len(test_files)
            assert all(r is True for r in results)

        print(f"\n✓ Azure Blob batch upload of {len(test_files)} files (mocked) completed")


# =============================================================================
# Cross-Cloud Tests
# =============================================================================

class TestCrossCloudOperations:
    """Tests for operations that span multiple cloud providers."""

    def test_cloud_provider_detection(self):
        """Test automatic detection of available cloud providers."""
        from opp.cloud_utils import detect_available_providers

        providers = detect_available_providers()

        # Should detect at least the mocked providers
        assert isinstance(providers, dict)
        print(f"\n✓ Detected cloud providers: {list(providers.keys())}")

    def test_upload_to_fallback_cloud(self, tmp_path: Path):
        """Test upload with fallback to available provider."""
        # Create test file
        file_path = tmp_path / "fallback_test.txt"
        file_path.write_text("Fallback test content")

        mock_s3_client = MagicMock()
        mock_s3_client.upload_file.return_value = None

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value = mock_s3_client

            from opp.cloud_utils import upload_to_available_cloud

            result = upload_to_available_cloud(
                file_path=file_path,
                preferred_provider="s3",
                bucket="fallback-bucket"
            )

            assert result is True

        print(f"\n✓ Fallback cloud upload completed")


# =============================================================================
# Pipeline Integration Tests
# =============================================================================

class TestCloudPipelineIntegration:
    """Test cloud operations integrated with OPP/ORF pipeline."""

    @pytest.fixture
    def pipeline_output(self, tmp_path: Path, opp_pipeline, sample_docx_path) -> dict:
        """Set up OPP pipeline output for cloud upload testing."""
        from conftest import run_opp_extraction

        output_dir = tmp_path / "pipeline_output"
        output_dir.mkdir(exist_ok=True)

        result = run_opp_extraction(
            opp_pipeline,
            sample_docx_path,
            output_dir,
            target_format="md"
        )

        return result

    def test_upload_extraction_to_s3(self, pipeline_output, s3_bucket_name):
        """Test uploading OPP extraction output to S3."""
        if not pipeline_output.get("md_path") or not pipeline_output["md_path"].exists():
            pytest.skip("No MD output from extraction")

        mock_s3_client = MagicMock()
        mock_s3_client.upload_file.return_value = None

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value = mock_s3_client

            from opp.cloud_utils import upload_to_s3

            result = upload_to_s3(
                file_path=pipeline_output["md_path"],
                bucket=s3_bucket_name,
                object_key="pipeline_test/extracted.md"
            )

            assert result is True

        print(f"\n✓ Pipeline output uploaded to S3 (mocked)")

    def test_download_and_process_from_cloud(self, tmp_path: Path):
        """Test downloading from cloud and processing through pipeline."""
        mock_s3_client = MagicMock()
        sample_content = b"# Test Document\n\nTest content for pipeline processing."
        mock_s3_client.download_fileobj.return_value = None

        def mock_download(Bucket, Key, Fileobj):
            Fileobj.write(sample_content)

        mock_s3_client.download_fileobj.side_effect = mock_download

        output_path = tmp_path / "downloaded_for_pipeline.md"

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value = mock_s3_client

            from opp.cloud_utils import download_from_s3

            result = download_from_s3(
                bucket="test-bucket",
                object_key="test/doc.md",
                output_path=output_path
            )

            assert result is True
            assert output_path.exists()

        print(f"\n✓ Downloaded and ready for pipeline processing")
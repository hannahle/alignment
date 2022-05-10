import os as _os
import requests
import mimetypes
from urllib.parse import urlparse
from urllib.request import urlretrieve
import math

from flytekit.common.exceptions.user import FlyteUserException as _FlyteUserException
from flytekit.configuration import latch as _latch_config
from flytekit.interfaces.data import common as _common_data

def _enforce_trailing_slash(path: str):
    if path[-1] != "/":
        path += "/"
    return path

class LatchProxy(_common_data.DataProxy):
    def __init__(self, raw_output_data_prefix_override: str = None):
        """
        :param raw_output_data_prefix_override: Instead of relying on the AWS or GCS configuration (see
            S3_SHARD_FORMATTER for AWS and GCS_PREFIX for GCP) setting when computing the shard
            path (_get_shard_path), use this prefix instead as a base. This code assumes that the
            path passed in is correct. That is, an S3 path won't be passed in when running on GCP.
        """
        self._raw_output_data_prefix_override = raw_output_data_prefix_override
        self._latch_endpoint = _os.environ.get("LATCH_AUTHENTICATION_ENDPOINT")
        if self._latch_endpoint is None:
            self._latch_endpoint = _latch_config.LATCH_AUTHENTICATION_ENDPOINT.get()
        if self._latch_endpoint is None:
            raise ValueError("LATCH_AUTHENTICATION_ENDPOINT must be set")
        self._chunk_size = _latch_config.LATCH_UPLOAD_CHUNK_SIZE_BYTES.get()
        if self._chunk_size is None:
            raise ValueError("S3_UPLOAD_CHUNK_SIZE_BYTES must be set")

    @property
    def raw_output_data_prefix_override(self) -> str:
        return self._raw_output_data_prefix_override

    @staticmethod
    def _split_s3_path_to_key(path) -> str:
        """
        :param str path:
        :rtype: str
        """
        url = urlparse(path)
        return url.path

    def exists(self, remote_path):
        """
        :param str remote_path: remote latch:/// path
        :rtype bool: whether the s3 file exists or not
        """

        if not remote_path.startswith("latch:///"):
            raise ValueError(f"expected a Latch URL (latch:///...): {remote_path}")

        r = requests.post(self._latch_endpoint + "/api/object-exists-at-url", json={"object_url": remote_path, "execution_name": _os.environ.get("FLYTE_INTERNAL_EXECUTION_ID")})
        if r.status_code != 200:
            raise _FlyteUserException("failed to check if object exists at url `{}`".format(remote_path))
        
        return r.json()["exists"]

    def download_directory(self, remote_path, local_path):
        """
        :param str remote_path: remote latch:/// path
        :param str local_path: directory to copy to
        """
        if not remote_path.startswith("latch:///"):
            raise ValueError(f"expected a Latch URL (latch:///...): {remote_path}")
        
        r = requests.post(self._latch_endpoint + "/api/get-presigned-urls-for-dir", json={"object_url": remote_path, "execution_name": _os.environ.get("FLYTE_INTERNAL_EXECUTION_ID")})
        if r.status_code != 200:
            raise _FlyteUserException("failed to download `{}`".format(remote_path))

        dir_key = self._split_s3_path_to_key(remote_path)[1:]
        dir_key = _enforce_trailing_slash(dir_key)
        key_to_url_map = r.json()["key_to_url_map"]
        for key, url in key_to_url_map.items():
            local_file_path = _os.path.join(local_path, key.replace(dir_key, "", 1))
            dir = "/".join(local_file_path.split("/")[:-1])
            _os.makedirs(dir, exist_ok=True)
            urlretrieve(url, local_file_path)
            assert _os.path.exists(local_file_path)
        return True

    def download(self, remote_path, local_path):
        """
        :param str remote_path: remote latch:/// path
        :param str local_path: directory to copy to
        """
        if not remote_path.startswith("latch:///"):
            raise ValueError(f"expected a Latch URL (latch:///...): {remote_path}")

        r = requests.post(self._latch_endpoint + "/api/get-presigned-url", json={"object_url": remote_path, "execution_name": _os.environ.get("FLYTE_INTERNAL_EXECUTION_ID")})
        if r.status_code != 200:
            raise _FlyteUserException("failed to get presigned url for `{}`".format(remote_path))
        
        url = r.json()["url"]
        urlretrieve(url, local_path)
        return _os.path.exists(local_path)

    def upload(self, file_path, to_path):
        """
        :param str file_path:
        :param str to_path:
        """
        file_size = _os.path.getsize(file_path)
        nrof_parts = math.ceil(float(file_size) / self._chunk_size)
        content_type = mimetypes.guess_type(file_path)[0]
        if content_type is None:
            content_type = "application/octet-stream"

        r = requests.post(self._latch_endpoint + "/api/begin-upload", json={"object_url": to_path, "nrof_parts": nrof_parts, "content_type": content_type, "execution_name": _os.environ.get("FLYTE_INTERNAL_EXECUTION_ID")})
        if r.status_code != 200:
            raise _FlyteUserException("failed to get presigned upload urls for `{}`".format(to_path))
        
        data = r.json()
        presigned_urls = data["urls"]
        upload_id = data["upload_id"]
        f = open(file_path, "rb")
        parts=[]
        for key, val in presigned_urls.items():
            blob = f.read(self._chunk_size)
            r = requests.put(val, data=blob)
            if r.status_code != 200:
                raise _FlyteUserException("failed to upload part `{}` of file `{}`".format(key, file_path))
            etag = r.headers['ETag']
            parts.append({'ETag': etag, 'PartNumber': int(key) + 1})
        
        r = requests.post(self._latch_endpoint + "/api/complete-upload", json={"upload_id": upload_id, "parts": parts, "object_url": to_path, "execution_name": _os.environ.get("FLYTE_INTERNAL_EXECUTION_ID")})
        if r.status_code != 200:
            raise _FlyteUserException("failed to complete upload for `{}`".format(to_path))
        return True

    def upload_directory(self, local_path, remote_path):
        """
        :param str local_path:
        :param str remote_path:
        """
        if remote_path == "latch://":
            remote_path = "latch:///"
        if not remote_path.startswith("latch:///"):
            raise ValueError(f"expected a Latch URL (latch:///...): {remote_path}")

        # ensure formatting
        local_path = _enforce_trailing_slash(local_path)
        remote_path = _enforce_trailing_slash(remote_path)

        files_to_upload = [_os.path.join(dp, f) for dp, __, filenames in _os.walk(local_path) for f in filenames]
        for file_path in files_to_upload:
            relative_name = file_path.replace(local_path, "", 1)
            if relative_name.startswith("/"):
                relative_name = relative_name[1:]
            # TODO(aidan): change this to form data (all at once)
            self.upload(file_path, remote_path + relative_name)
        return True

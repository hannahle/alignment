from flytekit.configuration import common as _config_common

LATCH_AUTHENTICATION_ENDPOINT = _config_common.FlyteStringConfigurationEntry("latch", "latch_authentication_endpoint", default="https://nucleus.latch.bio")

LATCH_UPLOAD_CHUNK_SIZE_BYTES = _config_common.FlyteIntegerConfigurationEntry("latch", "upload_chunk_size_bytes", default=10000000)

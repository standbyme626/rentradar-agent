from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "RentRadar"
    version: str = "0.1.0"
    env: str = Field("dev", validation_alias="APP_ENV")
    database_url: str = Field(
        "postgresql+asyncpg://rentradar:rentradar_dev@127.0.0.1:5433/rentradar",
        validation_alias="APP_DATABASE_URL",
    )
    secret_key: str = Field("dev-only-change-me", validation_alias="APP_SECRET_KEY")
    docs_enabled: bool = Field(False, validation_alias="APP_DOCS_ENABLED")
    cookie_secure: bool = Field(False, validation_alias="APP_COOKIE_SECURE")
    access_token_minutes: int = Field(15, validation_alias="APP_ACCESS_TOKEN_MINUTES")
    refresh_token_days: int = Field(7, validation_alias="APP_REFRESH_TOKEN_DAYS")
    login_max_failures: int = Field(5, validation_alias="APP_LOGIN_MAX_FAILURES")
    login_window_minutes: int = Field(15, validation_alias="APP_LOGIN_WINDOW_MINUTES")
    cors_origins: str = Field(
        "http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="APP_CORS_ORIGINS",
    )
    log_level: str = Field("INFO", validation_alias="APP_LOG_LEVEL")
    cdp_url: str = Field("http://127.0.0.1:9333", validation_alias="APP_CDP_URL")
    pymd3_bin: str = Field(
        "/home/data/venvs/pymd3/bin/pymobiledevice3",
        validation_alias="APP_PYMD3_BIN",
    )
    ipctl_bin: str = Field("/usr/local/bin/ipctl", validation_alias="APP_IPCTL_BIN")
    probe_device_id: str = Field("iphone11pro", validation_alias="PROBE_DEVICE_ID")

    feishu_app_id: str = Field("", validation_alias="FEISHU_APP_ID")
    feishu_app_secret: str = Field("", validation_alias="FEISHU_APP_SECRET")
    feishu_receive_id: str = Field("", validation_alias="FEISHU_RECEIVE_ID")
    feishu_receive_id_type: str = Field("open_id", validation_alias="FEISHU_RECEIVE_ID_TYPE")
    amap_web_key: str = Field("", validation_alias="AMAP_WEB_KEY")
    baidu_ak: str = Field("", validation_alias="BAIDU_AK")
    baidu_proxy: str = Field("", validation_alias="BAIDU_PROXY")
    tianditu_api_key: str = Field("", validation_alias="TIANDITU_API_KEY")
    tianditu_proxy: str = Field(
        "socks5h://127.0.0.1:10943", validation_alias="TIANDITU_PROXY"
    )
    didi_mcp_key: str = Field("", validation_alias="DIDI_MCP_KEY")
    didi_mcp_url: str = Field(
        "https://mcp.didichuxing.com/mcp-servers-sandbox",
        validation_alias="DIDI_MCP_URL",
    )
    modelscope_api_key: str = Field("", validation_alias="MODELSCOPE_API_KEY")
    modelscope_base_url: str = Field(
        "https://api-inference.modelscope.cn/v1",
        validation_alias="MODELSCOPE_BASE_URL",
    )
    modelscope_model: str = Field(
        "deepseek-ai/DeepSeek-V4.1-Flash-1017",
        validation_alias="MODELSCOPE_MODEL",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

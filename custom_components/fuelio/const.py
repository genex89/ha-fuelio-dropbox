"""Costanti per l'integrazione Fuelio (Dropbox)."""

DOMAIN = "fuelio"

CONF_APP_KEY = "app_key"
CONF_APP_SECRET = "app_secret"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_FOLDER = "folder"
CONF_FILE_NAME = "file_name"
CONF_DEVICE_NAME = "device_name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_AUTH_CODE = "code"

DEFAULT_FOLDER = "/Applicazioni/Fuelio/sync"
DEFAULT_DEVICE_NAME = "Fuelio"
DEFAULT_SCAN_INTERVAL_MINUTES = 60

DROPBOX_AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"

DROPBOX_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
DROPBOX_LIST_FOLDER_URL = "https://api.dropboxapi.com/2/files/list_folder"
DROPBOX_DOWNLOAD_URL = "https://content.dropboxapi.com/2/files/download"

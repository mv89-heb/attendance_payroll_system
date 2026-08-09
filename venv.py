python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql://neondb_owner:npg_ZyMdowu4Vnf9@ep-nameless-leaf-axihophz-pooler.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
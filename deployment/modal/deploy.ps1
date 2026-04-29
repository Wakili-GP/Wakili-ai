Set-Location "D:\chatbot_final\Wakili-chatbot"

python -m pip install --upgrade pip
python -m pip install modal

modal token new

$GroqKey = (Get-Content .env | Select-String "^GROQ_API_KEY").ToString().Split("=")[1].Trim().Trim('"')
$DatabaseUrl = (Get-Content .env | Select-String "^DATABASE_URL").ToString().Split("=",2)[1].Trim().Trim('"')

modal secret create wakili-secrets `
    GROQ_API_KEY="$GroqKey" `
    GROQ_MODEL_NAME="llama-3.3-70b-versatile" `
    DATABASE_URL="$DatabaseUrl"

modal deploy modal_app.py
$sql = Get-Content database/schema/schema.sql -Raw
$sql | docker compose exec -T postgres psql -U autohaggle -d autohaggle -v ON_ERROR_STOP=1

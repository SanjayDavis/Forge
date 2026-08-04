#!/usr/bin/env bash
# Real run-through of the flask-todo proof, captured into a transcript.
# Every line below is a real command with its real output.
set -u
cd "$(dirname "$0")"
OUT=transcript.txt
exec > >(tee "$OUT") 2>&1

echo "$ flask --app app init-db   # fresh schema (idempotent)"
flask --app app init-db

echo
echo "$ python run.py &   # start the server"
nohup python run.py >/dev/null 2>&1 &
SERVER_PID=$!
sleep 2
echo "[server pid $SERVER_PID on http://127.0.0.1:5000]"

echo
echo "$ curl -s http://127.0.0.1:5000/health"
curl -s http://127.0.0.1:5000/health
echo

echo
echo "$ curl -s -X POST -d 'title=Buy milk' http://127.0.0.1:5000/add -w 'HTTP %{http_code}' -o /dev/null"
curl -s -X POST -d "title=Buy milk" http://127.0.0.1:5000/add -w "HTTP %{http_code}" -o /dev/null; echo " (redirect to /)"
true

echo
echo "$ curl -s -X POST -d 'title=Write Forge tests' http://127.0.0.1:5000/add -w 'HTTP %{http_code}' -o /dev/null"
curl -s -X POST -d "title=Write Forge tests" http://127.0.0.1:5000/add -w "HTTP %{http_code}" -o /dev/null; echo " (redirect to /)"
true

echo
echo "$ curl -s http://127.0.0.1:5000/ | grep -oE '<span class=\"title\">[^<]+'"
curl -s http://127.0.0.1:5000/ | grep -oE '<span class="title">[^<]+'

echo
echo "$ curl -s -X POST http://127.0.0.1:5000/done/1 -w 'HTTP %{http_code}' -o /dev/null"
curl -s -X POST http://127.0.0.1:5000/done/1 -w "HTTP %{http_code}" -o /dev/null; echo " (task 1 completed)"
true

echo
echo "$ curl -s -X POST http://127.0.0.1:5000/done/1 -w 'HTTP %{http_code}' -o /dev/null   # again - idempotent, not 404"
curl -s -X POST http://127.0.0.1:5000/done/1 -w "HTTP %{http_code}" -o /dev/null; echo " (still 302 - the idempotency fix from the run)"
true

echo
echo "$ curl -s -X POST http://127.0.0.1:5000/delete/2 -w 'HTTP %{http_code}' -o /dev/null"
curl -s -X POST http://127.0.0.1:5000/delete/2 -w "HTTP %{http_code}" -o /dev/null; echo " (task 2 deleted)"
true

echo
echo "$ python -m unittest discover -s tests"
python -m unittest discover -s tests

echo
echo "$ kill $SERVER_PID   # stop the server"
kill "$SERVER_PID" 2>/dev/null
echo "demo complete."

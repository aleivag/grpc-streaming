set -ex

VENV=./.venv
PYTHON=$VENV/bin/python3

test -d $VENV || $(python3 -m venv $VENV && $PYTHON -m pip install -r requirements.txt )
$PYTHON -m grpc_tools.protoc -I . --python_out=.  --grpc_python_out=. proto/*.proto

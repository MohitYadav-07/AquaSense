#!/bin/sh
set -e
require_secret() {
  name="$1"
  eval "value=\${$name:-}"
  case "$value" in
    ""|CHANGE_ME*|change-me*|*placeholder*)
      echo "ERROR: Set a strong, unique $name in .env before starting this service." >&2
      exit 1
      ;;
  esac
}
case "$1" in
  api)
    require_secret API_KEY
    # first start: train the forecasting model (a few minutes), then reuse it from the volume
    if [ ! -f ml/models/moisture_model.keras ]; then (cd ml && python train.py); fi
    cd api && exec gunicorn -b 0.0.0.0:5001 -w 1 --timeout 180 app:app
    ;;
  dashboard)
    require_secret API_KEY
    require_secret DJANGO_SECRET_KEY
    cd dashboard
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    python manage.py create_demo_users          # prints demo logins once, only the first time
    exec gunicorn -b 0.0.0.0:8000 -w 2 config.wsgi
    ;;
  simulator)
    exec python iot/simulator.py --interval 5 --backfill 60
    ;;
  test)
    python -m unittest discover -s tests -t . && (cd dashboard && python manage.py test --settings=config.test_settings)
    ;;
  *)
    exec "$@"
    ;;
esac

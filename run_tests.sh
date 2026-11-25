#!/bin/sh
# Runs the unit/API tests and the dashboard tests (no MySQL or TensorFlow needed).
set -e
python -m unittest discover -s tests -t .
(cd dashboard && python manage.py test --settings=config.test_settings)

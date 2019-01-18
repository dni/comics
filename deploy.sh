#!/bin/sh
python render.py
aws s3 sync ./dist/ s3://dnilabs-hostinghelden/comics/
aws cloudfront create-invalidation --distribution-id E1GC39IE8JKEI6 --paths /comics/\*

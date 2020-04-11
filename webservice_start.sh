#!/usr/bin/env bash
if [ 1 ]
then
		if [ -z "`ps aux | grep cloud_sql_proxy | grep -v grep`" ]
		then
				screen -d -m ./gcloud/cloud_sql_proxy -instances=hazel-strand-270418:us-central1:contact-queue=tcp:3307
		fi		
		if [ -z "`ps aux | grep uwsgi | grep -v grep`" ]
		then
				screen -d -m sudo uwsgi --ini web_wsgi.ini --uid=philippp --gid=www-data
				sleep 20
		fi
		sleep 10
fi

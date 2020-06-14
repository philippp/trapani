#!/usr/bin/env bash
if [ 1 ]
then
		if [ -z "`ps aux | grep dispatcher_service.py | grep -v grep`" ]
		then
				screen -d -m python3 ./dispatcher_service.py --database prod --web_instance prod
		fi
		if [ -z "`ps aux | grep cloud_sql_proxy | grep -v grep`" ]
		then
				screen -d -m ./gcloud/cloud_sql_proxy -instances=hazel-strand-270418:us-central1:contact-queue=tcp:3307
		fi
		sleep 10
fi

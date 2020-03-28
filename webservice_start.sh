#!/usr/bin/env bash
if [ 1 ]
then
		if [ -z "`ps aux | grep uwsgi | grep -v grep`" ]
		then
				screen -d -m sudo uwsgi --ini web_wsgi.ini --uid=philippp --gid=www-data
				sleep 20
		fi
		sleep 10
fi

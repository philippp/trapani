#!/usr/bin/env bash
if [ 1 ]
then
		if [ -z "`ps aux | grep uwsgi | grep -v grep`" ]
		then
				screen -d -m uwsgi --ini web_wsgi.ini
				sudo chown philippp:www-data wsgi.sock
		fi
		sleep 10
fi

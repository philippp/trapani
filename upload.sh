#!/usr/bin/env bash
tar -cvzf bundle.tgz `git ls-tree -r master --name-only`
gcloud compute scp bundle.tgz dispatcher-1:~/ --zone=us-central1-a
gcloud compute scp --recurse keys dispatcher-1:~/
gcloud compute ssh dispatcher-1 --command 'tar -xvzf bundle.tgz'
gcloud compute scp bundle.tgz webservice-2:~/ --zone=us-central1-a
gcloud compute scp --recurse keys webservice-2:~/
gcloud compute ssh webservice-2 --command 'tar -xvzf bundle.tgz && rm bundle.tgz'
gcloud compute ssh webservice-2 --command 'sudo mv /home/philippp/web_nginx /etc/nginx/sites-available && sudo ln -s /etc/nginx/sites-available/web_nginx /etc/nginx/sites-enabled && sudo nginx -t && sudo systemctl restart nginx'
rm bundle.tgz

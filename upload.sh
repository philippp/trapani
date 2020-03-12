#!/usr/bin/env bash
tar -cvzf bundle.tgz `git ls-tree -r master --name-only`
gcloud compute scp bundle.tgz dispatcher-1:~/ --zone=us-central1-a
gcloud compute scp --recurse keys dispatcher-1:~/
gcloud compute scp bundle.tgz webservice-1:~/ --zone=us-central1-a
gcloud compute scp --recurse keys webservice-1:~/

# dnsmadeeasy hook for letsencrypt.sh ACME client

This a hook for the [Let's Encrypt](https://letsencrypt.org/) ACME client [dehydrated](https://github.com/lukas2511/dehydrated) (formerly letsencrypt.sh), that enables using DNS records on [dnsmadeeasy](https://www.dnsmadeeasy.com/) to respond to `dns-01` challenges. Requires Python 3 and your dnsmadeeasy account apikey and secretkey being set in the environment.

## Setup

```
$ git clone https://github.com/lukas2511/dehydrated
$ cd dehydrated
$ mkdir hooks
$ git clone https://github.com/alisade/letsencrypt-dnsmadeeasy-hook hooks/dnsmadeeasy
$ pip install -r hooks/dnsmadeeasy/requirements.txt
$ export API_USERNAME='xxx'
$ export API_Password='xxx'
```

## Usage

```
$ ./dehydrated -c -d example.com -t dns-01 -k 'hooks/active24/hook.py'
#
# !! WARNING !! No main config file found, using default config!
#
Processing example.com
 + Signing domains...
 + Creating new directory /home/user/dehydrated/certs/example.com ...
 + Generating private key...
 + Generating signing request...
 + Requesting challenge for example.com...
 + dnsmadeeasy hook executing: deploy_challenge
 + DNS not propagated, waiting 30s...
 + Responding to challenge for example.com...
 + dnsmadeeasy hook executing: clean_challenge
 + Challenge is valid!
 + Requesting certificate...
 + Checking certificate...
 + Done!
 + Creating fullchain.pem...
 + dnsmadeeasy hook executing: deploy_cert
 + ssl_certificate: /home/user/dehydrated/certs/example.com/fullchain.pem
 + ssl_certificate_key: /home/user/dehydrated/certs/example.com/privkey.pem
 + Done!
```

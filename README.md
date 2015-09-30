# icard-ustc
Consume record analyzer for USTCers.
Based on python tornado.
## Install iCard
iCard is based on Python. So to install python dependents for iCard, just try following:

```
$ sudo apt-get install python python-pip python-imaging
$ pip install beautifulsoup4 tornado motor
``` 

To install MongoDB, just follow the link:

[Install MongoDB on Linux](http://docs.mongodb.org/manual/administration/install-on-linux/)

After MongoDB works, icard can be ready for you. To start iCard, suppose your MongoDB node locates on the same host with iCard, just try following command:

```
$ python icard.py 127.0.0.1 8888
```

Then icard will run on `localhost:8888`.

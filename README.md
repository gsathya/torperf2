Read docs/torperf2.pdf for more details

# Developing with Vagrant:

To set up the development environment:

    $ vagrant up

If all goes well, then you can ssh into the box to continue development:

    $ vagrant ssh
    $ cd /torperf
    $ trial test # Run tests
    $ python torperf.py

# Non-Vagrant development:
If you would rather not use Vagrant, please install the following packages:     
- python
- python-dev
- python-pip
- tor

(You can try `apt-get -y install python python-dev python-pip tor`)

And then run `pip install -r requirements.txt` to install python packages.

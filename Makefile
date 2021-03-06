
destdir := /var/lib/doublefault
sources := account.json config.json
username := $(shell id -u -n)

targets := $(addprefix $(destdir)/,$(sources)) /var/spool/doublefault

default: $(targets)

$(destdir): $(targets)
	sudo mkdir -p $@
	sudo chown $(username) $@

$(destdir)/config.json: config.json
	cp $< $@

$(destdir)/account.json:
	echo "{ \"username\": \"user@exmaple.com",\"password\": \"changeme\"}" > $@


/var/spool/doublefault:
	sudo mkdir -p $@
	sudo chown $(username) $@


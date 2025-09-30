# No imports; Pyscript injects decorators/helpers.

@service
def apps_hello(name="world"):
    log.info("apps_hello says hi to %s", name)

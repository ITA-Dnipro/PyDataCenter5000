# Agent Plugins

Agents' functionality can now be extended via plugins. By default, agents come with built-in plugins for status and metric checks.

## Plugin Components

### `Plugin` Object

While each plugin is realized via a callable, it is then wrapped by a dedicated class `Plugin`. An instance of `Plugin` is itself a callable as it comes with the `__call__` magic method responsible for executing plugin's functionality.

`Plugin` can be instanriated via the `from_module` or `from_callable` factories. In the former case, `Plugin` is also responsible for validating the plugin module.

Every instance of `Plugin` has the `name` and `category` attributes. The `name` attribute is the name under which the plugin us registered within a class. The `category` attribute on the other hand is mainly designed to aggregate agent reports to further forward them to controller (this is discussed in more details in ...).

### `register_plugin` Dispatcher

While it is possibility, `Plugin` is not designed to be invoked directly by the user. Instead, plugin registration is handled by the dedicated dispatcher function `register_plugin`. In order to register plugin for some agent class `MyAgent`, one should invoke:

```python
register_plugin(my_plugin, MyAgent)
```

Here, `my_plugin` is your plugin module or callable. Subsequently, every instance of `MyAgent` will have the `my_plugin` method, which can be called as follows:

```python
result = agent.my_plugin(<your_args_or_kwargs>)
```

## HOW-TO: Working With Plugins

### Create Your Own

As you already know, plugins can be created as modules or callables. Both approaches can be used interchangably, however, consider the following strategy:

* Create plugins from modules when you're confident that they will benefit the class itself and, importantly, when they don't violate **S** from SOLID.

* Create plugins from callables when you're testing or debugging - it is fast, straightforward, and flexible.

**Plugin modules** must adhere to a specific structure. Consider the built-in `execute_timestamp_check.py` plugin:

```python
import datetime

import pytz

PLUGIN_NAME = 'check_timestamp'
PLUGIN_CATEGORY = 'status'


def execute(parent=None, timezone=None, *args, **kwargs):
    utc = pytz.utc.localize(datetime.datetime.utcnow())
    now = utc.astimezone(pytz.timezone(timezone or 'Europe/Kiev'))

    return {'timestamp': now}
```

The global variables `PLUGIN_NAME` and `PLUGIN_CATEGORY` should be set to the values which you intend as your plugin's name (subsequently, the name of a method within a class) and plugin's category.

Each plugin module can have as many callables as necessary, however, `Plugin` will invoke specifically the `execute` callable. Additionally, note the arguments of `execute`: the optional `parent` argument is in fact essential for the plugin to properly work within a class. Other arguments are entirely up to the user. For instance, in this context, `timezone` is relevant.

Finally, your plugin callable **should** return a dictionary. This is not strictly required, however, when plugins' output is aggregated into a single report by category, invalid output type will raise an error.

**Plugin callables** are very easy to implement. Consider the following simple function to determine the number of registered plugins - enabled or not - within a class:

```python
def check_plugin_number(parent):
    nplugins = 0

    for _, _ in inspect.getmembers(
        parent,
        predicate=lambda method: (
            inspect.ismethod(method) and getattr(method, 'is_plugin', False)
        )
    ):
        nplugins += 1

    return {'nplugins': nplugins}
```

This callable can be registered as a plugin within the `NTPAgent` as follows:

```python
register_plugin(check_plugin_number, NTPAgent, category='debug')
```

We then invoke it as follows:

```python
result = agent.check_plugin_number()
```

In the current implementation of plugins, `result = {'nplugins': 8}` (7 built-in plugins + `check_plugin_number`).

Note, that in this case we can pass plugin name and category as keyword parameters to `register_plugin`. As in the above example no custom name has been provided, it simply defaulted to the name of the function. If the category is not provided, it will default to `'unknown'`.

### Report Aggregation

Another useful use case for plugins is that we can aggregate server reports without hardcoding repspective methods in agent classes. Each category (`status`, `metric`, `health`, `debug` etc.) is handled by the `aggregate_reports` interface within `ServerAgent`. Assume you want to construct a dictionary containing all the metric of some server. This can be achieved in the following manner:

```
agent = agent.aggregate_reports(category='metric')
```

Here, we have to assume that `agent` is a valid instance of some (concrete) agent class. The example output could be

```
{'check_cpu_percent': {'cpu_percent': 16.7}, 'check_load_avg': {'load_avg': (1.7119140625, 1.49462890625, 1.5751953125)}, 'check_disk_usage': {'disk_usage': sdiskusage(total=494384795648, used=11252604928L, free=128549539840, percent=8.0)}, 'check_ram_percent': {'ram_percent': svmem(total=25769803776L, available=7444316160L, percent=71.1, used=9771089920L, free=149651456L, active=7303954432L, inactive=7199883264L, wired=2467135488L)}, 'server_name': 'my-server'}
```

This dict can be directly sent to controller using agents' `post_data`.

class Reference(object):
    def __init__(self, path):
	self.path = path
    def __get__(self, config):
	props = self.path.lstrip('/').split('.')
	while props:
	    config = config.get(props.pop(0))
	return config


class Config(dict):
    def __getattr__(self, attr):
	if attr in self:
	    result = self[attr]
            if isinstance(result, Reference):
                if result.path.startswith('/'):
                    result = result.__get__(cards)
                else:
                    result = result.__get__(self)
            if isinstance(result, dict) and not isinstance(result, Config):
                result = Config(result)
            return result
            

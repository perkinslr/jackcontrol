#Config, Reference, and configure provided in globals

cards = Config(
    hd_audio=Config(
	match=dict(),
	name='Auto-%(id)s-%(label)s',
	restart=-1,
	input=dict(
	    label="input",
	    subdevice='0',
	    channels=2,
	    buffer_size=512,
	    buffer_count=4,
	    sample_rate=48000,
	    quality=4
	),
	output=dict(
	    label="output",
	    subdevice='0',
	    channels=2,
	    buffer_size=512,
	    buffer_count=4,
	    sample_rate=48000,
	    quality=4
	)
    )
)


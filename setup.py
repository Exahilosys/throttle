import setuptools

with open('README.rst') as file:

    readme = file.read()

name = 'throttle'

version = '0.2.2'

author = 'Exahilosys'

url = f'https://github.com/{author}/{name}'

setuptools.setup(
    name = name,
    version = version,
    author = author,
    url = url,
    packages = setuptools.find_packages(),
    license = 'MIT',
    description = 'Frequency tracking and throttling utilities.',
    long_description = readme,
    extras_require = {
        'docs': [
            'sphinx'
        ]
    }
)

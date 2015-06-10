from codecs import open
from setuptools import setup, find_packages


# Get the long description from the relevant file
with open('README.rst', encoding='utf-8') as f:
    long_description = f.read()


setup(name='mikrotik',
      version='0.1',
      description="Client library for Mikrotik API",
      long_description=long_description,
      classifiers=[],
      keywords='mikrotik',
      author='Antti Jaakkola',
      author_email='mikrotik@annttu.fi',
      url='https://github.com/annttu/Mikrotik',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=True,
      install_requires=[],
      extras_require={
          'test': ['pytest']
      }
)

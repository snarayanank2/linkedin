
from setuptools import setup

setup(
    name="linkedin",
    version='0.1',
    py_modules=['linkedin'],
    install_requires=[
        'selenium==3.141.0', 'sheetfu==1.5.3', 'click==7.0', 'python-dateutil==2.8.1'
    ],
    entry_points='''
        [console_scripts]
        linkedin=linkedin:cli
    ''',
)
from setuptools import setup, find_packages

setup(
    name='grano-reconcile',
    version='0.3.2',
    description="An entity and social network tracking software for news applications (OpenRefine reconciliation API)",
    long_description=open('README.rst').read(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        ],
    keywords='sql graph sna networks journalism ddj refine googlerefine openrefine api reconciliation',
    author='Friedrich Lindenberg',
    author_email='friedrich@pudo.org',
    url='http://github.com/granoproject/grano-reconcile',
    license='MIT',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=[],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'grano>=0.3.1',
    ],
    entry_points={
        'grano.startup': [
            'reconcile = grano.reconcile.view:Configure'
        ]
    },
    tests_require=[]
)

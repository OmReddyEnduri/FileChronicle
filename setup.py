from setuptools import setup, find_packages

setup(
    name="filechronicle",
    version="0.1.0",
    description="Local-first universal file intelligence, differential snapshot engine, and revision recovery system.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="OmReddyEnduri",
    author_email="omreddy@users.noreply.github.com",
    url="https://github.com/OmReddyEnduri/FileChronicle",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "chronicle = filechronicle.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Version Control",
        "Topic :: System :: Archiving",
        "Topic :: Utilities",
    ],
)

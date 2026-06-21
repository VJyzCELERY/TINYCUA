#!/usr/bin/env python3
"""
Setup script for Notion Clone application.
Can be used with: pip install -e . or pip install .
"""

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="notion-clone",
    version="0.1.0",
    author="Developer",
    description="A Notion-like application with Python backend and SQLite storage",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "fastapi==0.*",
        "uvicorn[standard]==0.*",
        "sqlalchemy==2.*",
        "pydantic==2.*",
        "python-jose[cryptography]==3.*",
        "bcrypt==4.*",
        "passlib[bcrypt]==1.*",
    ],
    extras_require={
        "dev": [
            "black==23.*",
            "flake8==6.*",
            "mypy==1.*",
            "pytest==7.*",
        ]
    },
    entry_points={
        "console_scripts": [
            "notion=backend.main:app",
        ],
    },
)

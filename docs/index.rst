EntropPy Documentation
======================

**EntropPy** is a Python-based autocorrect dictionary generator for text expansion platforms. It algorithmically generates typos from English words and maps them to correct spellings, focusing on mechanical typing errors rather than spelling mistakes.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   algorithms
   efficiency
   api/index

Overview
--------

EntropPy generates five types of typing errors:

* **Transpositions**: Swapped characters (e.g., ``the`` → ``teh``)
* **Omissions**: Missing characters (e.g., ``because`` → ``becuse``)
* **Duplications**: Doubled characters (e.g., ``entropy`` → ``entroppy``)
* **Replacements**: Wrong characters (e.g., ``apple`` → ``applw``)
* **Insertions**: Additional characters (e.g., ``thewre`` → ``there``)

Features
--------

* **Multi-Platform Support**: Espanso, QMK, and extensible backend system
* **Smart Boundary Detection**: Prevents false triggers
* **Collision Resolution**: Frequency-based resolution of ambiguous typos
* **Pattern Generalization**: Reduces dictionary size by detecting repeated patterns
* **Platform-Specific Optimization**: Tailored output for each platform's constraints
* **Comprehensive Reports**: Detailed analysis of decisions and optimizations

Quick Start
-----------

Install EntropPy:

.. code-block:: bash

   pip install -e .

Generate corrections for Espanso:

.. code-block:: bash

   entroppy --platform espanso --top-n 5000 --output corrections

Generate corrections for QMK:

.. code-block:: bash

   entroppy --platform qmk --top-n 1000 --max-corrections 2000 --output corrections

Documentation
-------------

* :doc:`algorithms` - Detailed explanation of EntropPy's algorithms and logic
* :doc:`efficiency` - Information about processing efficiency and optimizations
* :doc:`api/index` - API reference documentation

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

# karsk test

!!! warning
    This section describes a planned feature. Actual behaviour in Karsk may differ.

## NAME
karsk\-test - Test Karsk packages using pytest

## SYNOPSIS
**karsk test** *config* *tests*

## DESCRIPTION
**karsk test** uses [pytest](https://pytest.org) to run tests inside of a *tests* directory.

In addition to the standard repertoire provided by *pytest*, this command provides the *karsk* pytest fixture, which is a pre-configured *karsk.context* object.

## OPTIONS

## SEE ALSO

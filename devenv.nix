{ pkgs, lib, config, inputs, ... }:

{
  languages.python = {
    enable = true;
    poetry.enable = true;
    poetry.install.enable = true;
  };

  # Build requirements
  packages = with pkgs; [
    autoconf
    automake
    libtool
    gfortran
    m4
  ];
}

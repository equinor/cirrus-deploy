{ pkgs, lib, config, inputs, ... }:

{
  languages.python = {
    enable = true;
    package = pkgs.python311;
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

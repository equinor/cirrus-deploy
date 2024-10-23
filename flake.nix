{
  inputs = {
    nixpkgs.url = "nixpkgs";
    flake-parts.url = "github:hercules-ci/flake-parts";
    devenv.url = "github:cachix/devenv";
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "x86_64-darwin"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      imports = [ inputs.devenv.flakeModule ];

      perSystem =
        {
          config,
          lib,
          pkgs,
          ...
        }:
        {
          formatter = pkgs.nixfmt-rfc-style;

          devenv.shells.default = {
            languages.rust.enable = true;

            pre-commit.hooks = {
              nixfmt-rfc-style.enable = true;
              rustfmt.enable = true;
            };
          };
        };
    };
}

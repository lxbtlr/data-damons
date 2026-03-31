{
  description = "A very basic flake";
  inputs.nixpkgs.url = "https://flakehub.com/f/NixOS/nixpkgs/0.1.*.tar.gz";

  outputs = {
    self,
    nixpkgs,
  }: let
    supportedSystems = ["x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin"];
    venvName = "nvenv";

    forEachSupportedSystem = f:
      nixpkgs.lib.genAttrs supportedSystems (system:
        f {
          pkgs = import nixpkgs {inherit system;};
        });
  in {
    devShells = forEachSupportedSystem ({pkgs}: {
      default =
        pkgs.mkShell.override
        {
          # Override stdenv in order to change compiler:
          #stdenv = pkgs.clangStdenv;
        }
        {
          packages = with pkgs;
            [
              (pkgs.python313.withPackages (ps: with ps; [
                jsonschema
                seaborn
                pandas
                numpy
                matplotlib
              ]))
              #clblas
              virtualenv
              md2pdf
              gcc
            ]
            ++ (
              if system == "aarch64-darwin"
              then []
              else [gdb]
            );
      # such a silly and bad fix to this
      LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc pkgs.zlib];
      postInstallHook = "echo hostname";
      shellHook = ''
      export PYTHON_COLORS=1
      export FORCE_COLOR=1
      if [ -d "${venvName}" ]; then 
        echo "Found V. Env!"
        source ${venvName}/bin/activate
      else
        echo "Did not find V. Env, building..."
        python -m venv ${venvName}
        source ${venvName}/bin/activate
        pip install -r requirements.txt
      fi
      '';
        };

    });
  };
}

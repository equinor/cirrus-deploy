from asyncio.subprocess import PIPE
from pathlib import Path

from karsk.builder import build_all
from karsk.context import TARGET_TRIPLETS, Context


async def test_hello_world_example(tmp_path, monkeypatch):
    """This builds an runs the hello world example.

    NOTE: This test does double-duty for testing that $src, if refering to a
    file, contains the file name. Previously it would keep the name of the
    original temporary file which is "/tmp/pkgsrc".
    """
    import shutil
    import yaml

    example_dir = Path(__file__).parent / "../../examples" / "hello_world"
    work_dir = tmp_path / "hello_world"
    shutil.copytree(example_dir, work_dir, ignore=shutil.ignore_patterns("output"))

    config_path = work_dir / "config.yaml"
    config_data = yaml.safe_load(config_path.read_text())
    config_data["destination"] = str(tmp_path)
    config_path.write_text(yaml.dump(config_data))

    monkeypatch.chdir(work_dir)

    ctx = Context.from_config_file(Path("config.yaml"), staging=tmp_path)
    await build_all(ctx)

    wrapper = (
        tmp_path / "hello" / TARGET_TRIPLETS[ctx.engine.arch] / "bin" / "binary.sh"
    )
    assert wrapper.exists()
    proc = await ctx.run(
        ctx.out("hello", staging=False) / "bin/binary.sh", stdout=PIPE, stderr=PIPE
    )
    stdout, stderr = await proc.communicate()
    assert proc.returncode == 0
    assert b"running with args:" in stdout

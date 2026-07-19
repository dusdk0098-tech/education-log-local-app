"use strict";

const { createHash } = require("node:crypto");
const { createReadStream, readFileSync } = require("node:fs");
const fs = require("node:fs/promises");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const source = path.join(root, "release", "win-unpacked");
const output = path.join(root, "release", "launcher");
const template = JSON.parse(readFileSync(path.join(root, "launcher", "app-manifest.template.json"), "utf8"));
const archiveBase = `${template.appId}-${template.version}-windows-x64`;
const archivePath = path.join(output, `${archiveBase}.zip`);
const manifestPath = path.join(output, `${archiveBase}.manifest.json`);
const rootManifestPath = path.join(root, "app-manifest.json");

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exitCode = 1;
});

async function main() {
  await assertReleaseTree(source);
  await fs.mkdir(output, { recursive: true });
  await fs.rm(archivePath, { force: true });
  await fs.rm(manifestPath, { force: true });
  const archive = spawnSync("tar.exe", ["-a", "-c", "-f", archivePath, "-C", source, "."], {
    encoding: "utf8",
    windowsHide: true
  });
  if (archive.status !== 0) throw new Error(`RELEASE_ARCHIVE_FAILED:${archive.stderr || archive.stdout}`);
  const files = await listReleaseFiles(source);
  const manifest = { ...template, packageSha256: await sha256(archivePath), files };
  const serialized = `${JSON.stringify(manifest, null, 2)}\n`;
  await fs.writeFile(manifestPath, serialized, "utf8");
  await fs.writeFile(rootManifestPath, serialized, "utf8");
  console.log(JSON.stringify({ archivePath, manifestPath, packageSha256: manifest.packageSha256, fileCount: files.length }));
}

async function assertReleaseTree(directory) {
  const details = await fs.lstat(directory);
  if (!details.isDirectory()) throw new Error("RELEASE_SOURCE_NOT_DIRECTORY");
  const files = await listRelativePaths(directory);
  const forbidden = files.find((file) => {
    const normalized = file.toLowerCase();
    return normalized === "resources/app-manifest.json"
      || normalized.endsWith(".log")
      || normalized.includes("/education_log.db")
      || normalized === "education_log.db";
  });
  if (forbidden) throw new Error(`RELEASE_TREE_CONTAINS_FORBIDDEN_FILE:${forbidden}`);
  for (const required of [
    template.entryPoint,
    "resources/backend/PeditEduBackend.exe",
    "resources/launcher-required.json"
  ]) {
    if (!files.includes(required)) throw new Error(`RELEASE_TREE_REQUIRED_FILE_MISSING:${required}`);
  }
}

async function listReleaseFiles(directory) {
  const files = await listRelativePaths(directory);
  return Promise.all(files.map(async (relativePath) => ({
    path: relativePath,
    sha256: await sha256(path.join(directory, ...relativePath.split("/")))
  })));
}

async function listRelativePaths(directory) {
  const files = [];
  await visit(directory, "");
  return files.sort((left, right) => left.localeCompare(right, "en"));

  async function visit(current, prefix) {
    const entries = await fs.readdir(current, { withFileTypes: true });
    entries.sort((left, right) => left.name.localeCompare(right.name, "en"));
    for (const entry of entries) {
      const absolute = path.join(current, entry.name);
      const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
      const details = await fs.lstat(absolute);
      if (details.isSymbolicLink()) throw new Error(`RELEASE_TREE_SYMLINK_FORBIDDEN:${relative}`);
      if (details.isDirectory()) await visit(absolute, relative);
      else if (details.isFile()) files.push(relative);
      else throw new Error(`RELEASE_TREE_ENTRY_UNSUPPORTED:${relative}`);
    }
  }
}

async function sha256(filePath) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(filePath)) hash.update(chunk);
  return hash.digest("hex");
}

"use strict";

const { readFileSync } = require("node:fs");
const fs = require("node:fs/promises");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const source = path.join(root, "release", "win-unpacked");
const output = path.join(root, "release", "central-signing-candidate");
const template = JSON.parse(readFileSync(path.join(root, "launcher", "app-manifest.template.json"), "utf8"));
const metadata = {
  schemaVersion: 1,
  appId: template.appId,
  name: template.name,
  version: template.version,
  minimumLauncherVersion: template.minimumLauncherVersion,
  protocolVersion: template.protocolVersion,
  entryPoint: template.entryPoint,
};

main().catch((error) => {
  console.error(error?.stack || String(error));
  process.exitCode = 1;
});

async function main() {
  await assertReleaseTree(source);
  await fs.mkdir(output, { recursive: true });
  const archiveName = `${metadata.appId}-${metadata.version}-windows-x64.unsigned.zip`;
  const expected = new Set([archiveName, "pedit-release-candidate.json"]);
  const entries = await fs.readdir(output, { withFileTypes: true });
  if (entries.some((entry) => !entry.isFile() || !expected.has(entry.name))) throw new Error("CENTRAL_SIGNING_CANDIDATE_OUTPUT_NOT_EMPTY");
  await Promise.all([...expected].map((name) => fs.rm(path.join(output, name), { force: true })));
  const archivePath = path.join(output, archiveName);
  const archive = spawnSync("tar.exe", ["-a", "-c", "-f", archivePath, "-C", source, "."], { encoding: "utf8", windowsHide: true });
  if (archive.status !== 0) throw new Error(`CENTRAL_SIGNING_CANDIDATE_ARCHIVE_FAILED:${archive.stderr || archive.stdout}`);
  await fs.writeFile(path.join(output, "pedit-release-candidate.json"), `${JSON.stringify(metadata, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ candidateDirectory: output, unsignedZip: archiveName, appId: metadata.appId, version: metadata.version, entryPoint: metadata.entryPoint }));
}

async function assertReleaseTree(directory) {
  const details = await fs.lstat(directory);
  if (!details.isDirectory()) throw new Error("RELEASE_SOURCE_NOT_DIRECTORY");
  const files = await listRelativePaths(directory);
  const forbidden = files.find((file) => {
    const normalized = file.toLowerCase();
    return normalized === "resources/app-manifest.json" || normalized.endsWith(".log") || normalized.includes("/education_log.db") || normalized === "education_log.db";
  });
  if (forbidden) throw new Error(`RELEASE_TREE_CONTAINS_FORBIDDEN_FILE:${forbidden}`);
  for (const required of [metadata.entryPoint, "resources/backend/PeditEduBackend.exe", "resources/launcher-required.json"]) {
    if (!files.includes(required)) throw new Error(`RELEASE_TREE_REQUIRED_FILE_MISSING:${required}`);
  }
}

async function listRelativePaths(directory) {
  const files = [];
  await visit(directory, "");
  return files;
  async function visit(current, prefix) {
    const entries = await fs.readdir(current, { withFileTypes: true });
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

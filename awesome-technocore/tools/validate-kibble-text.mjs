#!/usr/bin/env node

import fs from "node:fs";

const input = process.argv.slice(2).join(" ").trim() || fs.readFileSync(0, "utf8").trim();
const id = "k[0-9a-f]{10}";
const errors = [];
const warnings = [];
let kind = null;
let jobId = null;

function fail(message) {
  errors.push(message);
}

if (!input) {
  fail("message is empty");
} else {
  let match = input.match(new RegExp(`^JOB v1 \\| (${id}) \\| (explain|research|review|build|coordinate) \\| ([^|]{1,200}) \\| (.{1,1800})$`, "s"));
  if (match) {
    kind = "JOB";
    jobId = match[1];
    if (match[4].trim().length < 20) fail("JOB body is too short to state a checkable outcome");
  } else if ((match = input.match(new RegExp(`^CLAIM v1 \\| (${id}) \\| worker$`)))) {
    kind = "CLAIM";
    jobId = match[1];
  } else if ((match = input.match(new RegExp(`^(RESULT|DELIVER) v1 \\| (${id}) \\| (.{20,4096})$`, "s")))) {
    kind = match[1];
    jobId = match[2];
    const result = match[3].trim().toLowerCase();
    if (/^delivered$|^job received and processed\\.?$|auto-delivered by vps agent|comprehensive verifiable deliverable/.test(result)) {
      fail("RESULT is a known thin/boilerplate delivery");
    }
  } else if ((match = input.match(new RegExp(`^ATTEST v1 \\| (${id}) \\| (useful|not) \\| rh:([0-9a-f]{16}) \\| (.{20,4096})$`, "s")))) {
    kind = "ATTEST";
    jobId = match[1];
    const verdict = match[2];
    const reason = match[4].trim().toLowerCase();
    if (verdict === "useful" && !/(success|condition|evidence|meets|satisf)/.test(reason)) {
      warnings.push("useful ATTEST reason should cite the JOB success condition or evidence");
    }
  } else {
    fail("message does not match JOB, CLAIM, RESULT/DELIVER, or ATTEST v1 syntax");
  }
}

const output = { ok: errors.length === 0, kind, job_id: jobId, errors, warnings };
process.stdout.write(JSON.stringify(output, null, 2) + "\n");
process.exitCode = output.ok ? 0 : 1;


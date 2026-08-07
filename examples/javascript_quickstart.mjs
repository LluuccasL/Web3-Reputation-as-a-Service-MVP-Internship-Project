import {
  Web3TrustClient,
  Web3TrustError,
} from "../sdks/javascript/src/index.js";


const apiKey = process.env.WEB3_TRUST_API_KEY ?? "";
const demoWallet = "0xd000000000000000000000000000000000000001";

if (!apiKey) {
  console.error("Set WEB3_TRUST_API_KEY before running this example.");
  process.exit(1);
}

const client = new Web3TrustClient({
  baseUrl: process.env.WEB3_TRUST_API_URL ?? "http://127.0.0.1:8000",
  apiKey,
});

try {
  const version = await client.version();
  const trust = await client.checkWallet(demoWallet);
  const signedProof = await client.generateProof(demoWallet);
  const verification = await client.verifyProof(signedProof);

  console.log(`API version: ${version.version}`);
  console.log(`Trust tier: ${trust.trust_tier}`);
  console.log(`Human likelihood: ${trust.human_likelihood}`);
  console.log(`Proof valid: ${verification.valid}`);
} catch (error) {
  if (error instanceof Web3TrustError) {
    console.error(
      "Request failed:",
      {
        code: error.code,
        status: error.statusCode,
        requestId: error.requestId,
        message: error.message,
      },
    );
  } else {
    console.error(error);
  }

  process.exit(1);
}

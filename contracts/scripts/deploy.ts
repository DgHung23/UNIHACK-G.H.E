import { ethers, network } from "hardhat";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

async function main() {
  const [deployer] = await ethers.getSigners();
  if (!deployer) throw new Error("Set EVM_PRIVATE_KEY to a funded Fuji test wallet key.");
  const chainId = Number((await ethers.provider.getNetwork()).chainId);
  if (![31337, 1337, 43113].includes(chainId)) throw new Error("Deployment supports local development and Fuji testnet only.");
  const contract = await (await ethers.getContractFactory("FruitChain", deployer)).deploy();
  await contract.waitForDeployment();
  const receipt = await contract.deploymentTransaction()!.wait();
  const address = await contract.getAddress();
  const deployment = {
    address, chainId, network: network.name, deployer: deployer.address,
    blockNumber: receipt!.blockNumber, txHash: receipt!.hash,
    explorerUrl: chainId === 43113 ? `https://testnet.snowtrace.io/address/${address}` : null,
    deployedAt: new Date().toISOString(),
  };
  const directory = resolve(__dirname, "../../backend/storage");
  mkdirSync(directory, { recursive: true });
  writeFileSync(resolve(directory, "evm_deployment.json"), JSON.stringify(deployment, null, 2));
  console.log(JSON.stringify(deployment, null, 2));
  console.log(`Backend: LEDGER_MODE=evm EVM_CHAIN_ID=${chainId} EVM_CONTRACT_ADDRESS=${address}`);
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });

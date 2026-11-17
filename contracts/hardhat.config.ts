import { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-ethers";
import "@nomicfoundation/hardhat-chai-matchers";

const config: HardhatUserConfig = {
  solidity: { version: "0.8.24", settings: { evmVersion: "cancun", optimizer: { enabled: true, runs: 200 }, viaIR: true } },
  networks: {
    localhost: { url: "http://127.0.0.1:8545" },
    hardhat: { chainId: 31337 },
    fuji: {
      url: process.env.EVM_RPC || "https://api.avax-test.network/ext/bc/C/rpc",
      chainId: 43113,
      accounts: process.env.EVM_PRIVATE_KEY ? [process.env.EVM_PRIVATE_KEY] : [],
    },
  },
};

export default config;

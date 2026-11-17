import { expect } from "chai";
import { ethers } from "hardhat";

const h = (s: string) => ethers.keccak256(ethers.toUtf8Bytes(s));
const ZERO = ethers.ZeroHash;
enum Role { NONE, ADMIN, FARMER, WAREHOUSE, TRANSPORT, DISTRIBUTOR, RETAILER, REGULATOR }

describe("FruitChain", () => {
  async function deploy() {
    const [admin, farmer, truck, store, outsider, auditor] = await ethers.getSigners();
    const fc = await (await ethers.getContractFactory("FruitChain")).deploy();
    await fc.grantRole(farmer.address, Role.FARMER);
    await fc.grantRole(truck.address, Role.TRANSPORT);
    await fc.grantRole(store.address, Role.RETAILER);
    await fc.grantRole(auditor.address, Role.REGULATOR);
    for (const [id, wallet] of [["F001", farmer.address], ["T001", truck.address], ["R001", store.address], ["A001", auditor.address]]) {
      await fc.registerActor(id, wallet);
    }
    const model = h("model-q10");
    await fc.registerModel(model, "rul-q10-v0.1");
    return { fc, admin, farmer, truck, store, outsider, auditor, model };
  }

  it("tạo lô thành công", async () => {
    const { fc, farmer, model } = await deploy();
    await expect(fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 1400, model))
      .to.emit(fc, "BatchEventRecorded");
    expect(await fc.getEventCount("FC-1")).to.equal(1n);
    expect(await fc.headHash("FC-1")).to.equal(h("e1"));
    const ev = await fc.getFunction("getEvent")("FC-1", 0);
    expect(ev.dataHash).to.equal(h("meta"));
    expect(ev.rulCentiDays).to.equal(1400n);
  });

  it("tạo trùng bị từ chối", async () => {
    const { fc, farmer, model } = await deploy();
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, model);
    await expect(fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 2, h("meta"), h("e2"), 0, model)).to.be.revertedWith("batch exists");
  });

  it("prevHash sai bị từ chối", async () => {
    const { fc, farmer, truck, model } = await deploy();
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, model);
    await expect(fc.connect(farmer).getFunction("recordHandoff")("FC-1", "F001", "T001", 2, h("d"), h("wrong"), h("e2"), 0, model))
      .to.be.revertedWith("bad prevHash");
    await fc.connect(farmer).getFunction("recordHandoff")("FC-1", "F001", "T001", 2, h("d"), h("e1"), h("e2"), 0, model);
    expect(await fc.headHash("FC-1")).to.equal(h("e2"));
  });

  it("sai vai trò bị từ chối", async () => {
    const { fc, farmer, truck, outsider, model } = await deploy();
    await expect(fc.connect(truck).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, model)).to.be.revertedWith("forbidden");
    await expect(fc.connect(outsider).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, model)).to.be.revertedWith("forbidden");
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, model);
    await expect(fc.connect(truck).getFunction("recordSold")("FC-1", "T001", 3, h("s"), h("e1"), h("e2"), 0, model)).to.be.revertedWith("forbidden");
    await expect(fc.connect(outsider).getFunction("grantRole")(outsider.address, Role.ADMIN)).to.be.revertedWith("only admin");
  });

  it("sau SOLD không ghi thêm được", async () => {
    const { fc, farmer, store, auditor, model } = await deploy();
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, model);
    await fc.connect(farmer).getFunction("recordHandoff")("FC-1", "F001", "R001", 2, h("leg"), h("e1"), h("e2"), 0, model);
    await fc.connect(store).getFunction("recordSold")("FC-1", "R001", 3, h("s"), h("e2"), h("e3"), 0, model);
    await expect(fc.connect(auditor).getFunction("recordViolation")("FC-1", "A001", 4, h("v"), h("e3"), h("e4"), 0, model))
      .to.be.revertedWith("batch closed");
  });

  it("modelHash chưa đăng ký bị từ chối", async () => {
    const { fc, farmer } = await deploy();
    await expect(fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, h("unknown")))
      .to.be.revertedWith("unknown model");
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, ZERO); // ZERO = không gắn model
  });

  it("ghi INSPECTION (ảnh) với model ảnh đã đăng ký", async () => {
    const { fc, admin, farmer, auditor, model } = await deploy();
    const img = h("model-image");
    await fc.connect(admin).getFunction("registerModel")(img, "custom-D");
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, model);
    await fc.connect(auditor).getFunction("recordInspection")("FC-1", "A001", 2, h("imgbytes"), h("e1"), h("e2"), 185, img);
    expect((await fc.getFunction("getEvent")("FC-1", 1)).eventType).to.equal(4n);
  });

  it("không thể chuyển giao hoặc bán từ bên không giữ lô", async () => {
    const { fc, farmer, truck, store, model } = await deploy();
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 10, h("meta"), h("e1"), 0, model);
    await expect(fc.connect(truck).getFunction("recordHandoff")("FC-1", "T001", "R001", 11, h("d"), h("e1"), h("e2"), 0, model))
      .to.be.revertedWith("wrong custodian");
    await expect(fc.connect(store).getFunction("recordSold")("FC-1", "R001", 11, h("s"), h("e1"), h("e2"), 0, model))
      .to.be.revertedWith("wrong custodian");
    await fc.connect(farmer).getFunction("recordHandoff")("FC-1", "F001", "T001", 11, h("d"), h("e1"), h("e2"), 0, model);
    expect(await fc.currentActor("FC-1")).to.equal("T001");
  });

  it("từ chối bằng chứng rỗng, hash tái sử dụng và thời gian lùi", async () => {
    const { fc, farmer, auditor, model } = await deploy();
    await expect(fc.connect(farmer).getFunction("createBatch")("", "F001", 10, h("meta"), h("e1"), 0, model))
      .to.be.revertedWith("empty identifier");
    await expect(fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 10, ZERO, h("e1"), 0, model))
      .to.be.revertedWith("zero evidence hash");
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 10, h("meta"), h("e1"), 0, model);
    await expect(fc.connect(auditor).getFunction("recordInspection")("FC-1", "A001", 9, h("i"), h("e1"), h("e2"), 0, model))
      .to.be.revertedWith("timestamp before head");
    await expect(fc.connect(auditor).getFunction("recordInspection")("FC-1", "A001", 11, h("i"), h("e1"), h("e1"), 0, model))
      .to.be.revertedWith("duplicate event hash");
    expect(await fc.getEventCount("FC-1")).to.equal(1n);
  });

  it("phiên bản model đã đăng ký không thể bị ghi đè", async () => {
    const { fc, model } = await deploy();
    expect(await fc.modelVersions(model)).to.equal("rul-q10-v0.1");
    await expect(fc.registerModel(model, "changed-version")).to.be.revertedWith("model already registered");
    await expect(fc.registerModel(ZERO, "zero")).to.be.revertedWith("zero model hash");
    await expect(fc.registerModel(h("new"), "")).to.be.revertedWith("empty model version");
  });

  it("không chuyển giao cho bên rỗng hoặc chính mình", async () => {
    const { fc, farmer, model } = await deploy();
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, model);
    for (const [to, reason] of [["", "empty recipient"], ["F001", "same custodian"]]) {
      await expect(fc.connect(farmer).getFunction("recordHandoff")("FC-1", "F001", to, 2, h("d"), h("e1"), h("e2"), 0, model))
        .to.be.revertedWith(reason);
    }
  });

  it("vai trò được ghi log và không thể vô hiệu admin gốc", async () => {
    const { fc, admin, outsider } = await deploy();
    await expect(fc.grantRole(outsider.address, Role.FARMER)).to.emit(fc, "RoleGranted").withArgs(outsider.address, Role.FARMER);
    await expect(fc.grantRole(ethers.ZeroAddress, Role.FARMER)).to.be.revertedWith("zero address");
    await expect(fc.grantRole(admin.address, Role.NONE)).to.be.revertedWith("admin role required");
  });

  it("ví được cấp quyền vẫn không được giả danh actor khác", async () => {
    const { fc, farmer, truck, model } = await deploy();
    await fc.connect(farmer).getFunction("createBatch")("FC-1", "F001", 1, h("meta"), h("e1"), 0, model);
    await expect(fc.connect(truck).getFunction("recordHandoff")("FC-1", "F001", "T001", 2, h("d"), h("e1"), h("e2"), 0, model))
      .to.be.revertedWith("actor wallet mismatch");
    await expect(fc.registerActor("F001", truck.address)).to.be.revertedWith("actor already registered");
    await expect(fc.connect(truck).getFunction("registerActor")("T002", truck.address)).to.be.revertedWith("only admin");
  });
});

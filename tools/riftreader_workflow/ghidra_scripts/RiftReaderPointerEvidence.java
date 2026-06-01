// Extract RiftReader pointer-chain static-analysis evidence from a Ghidra project.
//@category RiftReader

import java.io.FileWriter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class RiftReaderPointerEvidence extends GhidraScript {

	private static final long ROOT_RVA = 0x32EBC80L;
	private static final long[] OWNER_OFFSETS = new long[] {
		0x300L, 0x304L, 0x30cL, 0x310L, 0x314L, 0x320L, 0x324L, 0x328L, 0x438L, 0x43cL, 0x440L
	};
	private static final int MAX_ROOT_REFS = 200;
	private static final int MAX_HITS_PER_OFFSET = 80;
	private static final int MAX_DECOMPILED_FUNCTIONS = 16;
	private static final int MAX_DECOMPILED_CHARS = 5000;

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length < 1) {
			throw new IllegalArgumentException("usage: RiftReaderPointerEvidence.java <output-json-path>");
		}

		JsonObject result = new JsonObject();
		result.addProperty("schemaVersion", 1);
		result.addProperty("kind", "riftreader-ghidra-pointer-evidence");
		result.addProperty("programName", currentProgram.getName());
		result.addProperty("imageBase", currentProgram.getImageBase().toString());
		result.addProperty("rootRva", hex(ROOT_RVA));
		result.addProperty("rootAddress", currentProgram.getImageBase().add(ROOT_RVA).toString());
		result.addProperty("promotionPerformed", false);
		result.add("safety", safetyJson());

		Address rootAddress = currentProgram.getImageBase().add(ROOT_RVA);
		result.add("rootReferences", collectRootReferences(rootAddress));
		JsonObject offsetHits = collectOffsetHits();
		result.add("ownerOffsetHits", offsetHits);
		result.add("decompilerSnippets", collectDecompilerSnippets(offsetHits));

		try (FileWriter writer = new FileWriter(args[0])) {
			Gson gson = new GsonBuilder().setPrettyPrinting().create();
			gson.toJson(result, writer);
		}
		println("Wrote RiftReader pointer evidence to " + args[0]);
	}

	private JsonObject safetyJson() {
		JsonObject safety = new JsonObject();
		safety.addProperty("offlineOnly", true);
		safety.addProperty("movementSent", false);
		safety.addProperty("inputSent", false);
		safety.addProperty("x64dbgAttach", false);
		safety.addProperty("noCheatEngine", true);
		safety.addProperty("targetMemoryBytesRead", false);
		safety.addProperty("targetMemoryBytesWritten", false);
		safety.addProperty("providerWrites", false);
		safety.addProperty("proofPromotion", false);
		return safety;
	}

	private JsonArray collectRootReferences(Address rootAddress) {
		JsonArray refsJson = new JsonArray();
		ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(rootAddress);
		int count = 0;
		while (refs.hasNext() && count < MAX_ROOT_REFS && !monitor.isCancelled()) {
			Reference ref = refs.next();
			JsonObject item = new JsonObject();
			item.addProperty("from", ref.getFromAddress().toString());
			item.addProperty("to", ref.getToAddress().toString());
			item.addProperty("referenceType", ref.getReferenceType().toString());
			Function function = getFunctionContaining(ref.getFromAddress());
			if (function != null) {
				item.addProperty("functionName", function.getName());
				item.addProperty("functionEntry", function.getEntryPoint().toString());
			}
			Instruction instruction = getInstructionAt(ref.getFromAddress());
			if (instruction != null) {
				item.addProperty("instruction", instruction.toString());
				item.addProperty("mnemonic", instruction.getMnemonicString());
			}
			refsJson.add(item);
			count++;
		}
		return refsJson;
	}

	private JsonObject collectOffsetHits() {
		JsonObject byOffset = new JsonObject();
		Map<Long, Integer> hitCounts = new LinkedHashMap<Long, Integer>();
		for (long offset : OWNER_OFFSETS) {
			hitCounts.put(offset, 0);
			byOffset.add(hex(offset), new JsonArray());
		}

		Listing listing = currentProgram.getListing();
		InstructionIterator instructions = listing.getInstructions(true);
		long scanned = 0;
		while (instructions.hasNext() && !monitor.isCancelled()) {
			Instruction instruction = instructions.next();
			scanned++;
			for (long offset : OWNER_OFFSETS) {
				int currentCount = hitCounts.get(offset);
				if (currentCount >= MAX_HITS_PER_OFFSET || !instructionMatchesOffset(instruction, offset)) {
					continue;
				}
				JsonArray hits = byOffset.getAsJsonArray(hex(offset));
				hits.add(instructionJson(instruction, offset));
				hitCounts.put(offset, currentCount + 1);
			}
		}

		byOffset.addProperty("_instructionsScanned", scanned);
		return byOffset;
	}

	private JsonObject instructionJson(Instruction instruction, long offset) {
		JsonObject item = new JsonObject();
		item.addProperty("offset", hex(offset));
		item.addProperty("address", instruction.getAddress().toString());
		item.addProperty("mnemonic", instruction.getMnemonicString());
		item.addProperty("instruction", instruction.toString());
		item.addProperty("accessGuess", guessAccess(instruction, offset));
		Function function = getFunctionContaining(instruction.getAddress());
		if (function != null) {
			item.addProperty("functionName", function.getName());
			item.addProperty("functionEntry", function.getEntryPoint().toString());
		}
		return item;
	}

	private boolean instructionMatchesOffset(Instruction instruction, long offset) {
		for (int i = 0; i < instruction.getNumOperands(); i++) {
			Scalar scalar = instruction.getScalar(i);
			if (scalar != null && scalar.getUnsignedValue() == offset) {
				return true;
			}
			String operand = instruction.getDefaultOperandRepresentation(i);
			if (containsOffsetText(operand, offset)) {
				return true;
			}
		}
		return containsOffsetText(instruction.toString(), offset);
	}

	private boolean containsOffsetText(String value, long offset) {
		if (value == null) {
			return false;
		}
		String lower = value.toLowerCase(Locale.ROOT).replace(" ", "");
		String bare = Long.toHexString(offset);
		return lower.contains("0x" + bare) || lower.contains(bare + "h") || lower.contains("+" + bare);
	}

	private String guessAccess(Instruction instruction, long offset) {
		String mnemonic = instruction.getMnemonicString().toLowerCase(Locale.ROOT);
		String firstOperand = instruction.getNumOperands() > 0 ? instruction.getDefaultOperandRepresentation(0) : "";
		boolean firstOperandHasOffset = containsOffsetText(firstOperand, offset);
		if (firstOperandHasOffset && (mnemonic.startsWith("mov") || mnemonic.startsWith("add") ||
				mnemonic.startsWith("sub") || mnemonic.startsWith("xor") || mnemonic.startsWith("lea") ||
				mnemonic.startsWith("cmpxchg") || mnemonic.startsWith("xchg"))) {
			return "write-or-destination";
		}
		if (firstOperandHasOffset) {
			return "destination-or-test";
		}
		return "read-or-source";
	}

	private JsonArray collectDecompilerSnippets(JsonObject offsetHits) {
		JsonArray snippets = new JsonArray();
		Set<String> seenEntries = new HashSet<String>();
		ArrayList<Function> functions = new ArrayList<Function>();
		for (long offset : OWNER_OFFSETS) {
			JsonArray hits = offsetHits.getAsJsonArray(hex(offset));
			if (hits == null) {
				continue;
			}
			for (int i = 0; i < hits.size(); i++) {
				JsonObject hit = hits.get(i).getAsJsonObject();
				if (!hit.has("functionEntry")) {
					continue;
				}
				String entry = hit.get("functionEntry").getAsString();
				if (seenEntries.contains(entry)) {
					continue;
				}
				Function function = getFunctionAt(toAddr(entry));
				if (function != null) {
					functions.add(function);
					seenEntries.add(entry);
				}
				if (functions.size() >= MAX_DECOMPILED_FUNCTIONS) {
					break;
				}
			}
			if (functions.size() >= MAX_DECOMPILED_FUNCTIONS) {
				break;
			}
		}

		DecompInterface decompiler = new DecompInterface();
		decompiler.openProgram(currentProgram);
		for (Function function : functions) {
			if (monitor.isCancelled()) {
				break;
			}
			JsonObject item = new JsonObject();
			item.addProperty("functionName", function.getName());
			item.addProperty("functionEntry", function.getEntryPoint().toString());
			DecompileResults results = decompiler.decompileFunction(function, 12, monitor);
			item.addProperty("completed", results.decompileCompleted());
			if (results.decompileCompleted() && results.getDecompiledFunction() != null) {
				String c = results.getDecompiledFunction().getC();
				item.addProperty("cPreview", c.length() > MAX_DECOMPILED_CHARS ? c.substring(0, MAX_DECOMPILED_CHARS) : c);
			}
			else {
				item.addProperty("error", results.getErrorMessage());
			}
			snippets.add(item);
		}
		decompiler.dispose();
		return snippets;
	}

	private String hex(long value) {
		return "0x" + Long.toHexString(value).toUpperCase(Locale.ROOT);
	}
}

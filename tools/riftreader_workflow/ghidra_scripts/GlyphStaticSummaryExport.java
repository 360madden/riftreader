// Export safe offline Glyph launcher static-analysis summary from a Ghidra project.
//@category RiftReader

import java.io.FileWriter;
import java.util.Locale;
import java.util.regex.Pattern;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.ExternalManager;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.util.DefinedStringIterator;

public class GlyphStaticSummaryExport extends GhidraScript {

	private static final int MAX_FUNCTIONS = 600;
	private static final int MAX_SYMBOLS = 600;
	private static final int MAX_STRINGS = 800;
	private static final int MAX_REFS_PER_STRING = 12;
	private static final Pattern EMAIL_RE =
		Pattern.compile("(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b");
	private static final Pattern BEARER_RE =
		Pattern.compile("(?i)\\bBearer\\s+[A-Za-z0-9._~+/=-]{8,}");
	private static final Pattern LONG_VALUE_RE = Pattern.compile("\\b[A-Za-z0-9._~+/=-]{48,}\\b");
	private static final String[] KEYWORDS = new String[] {
		"glyph", "trion", "rift", "gamigo", "auth", "login", "ticket", "token",
		"manifest", "patch", "download", "update", "crash", "steam", "commerce",
		"store", "support", "http", "url", "registry", "software\\trion"
	};

	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		if (args.length < 1) {
			throw new IllegalArgumentException("usage: GlyphStaticSummaryExport.java <output-json-path>");
		}

		JsonObject result = new JsonObject();
		result.addProperty("schemaVersion", 1);
		result.addProperty("kind", "glyph-ghidra-static-summary-export");
		result.addProperty("programName", currentProgram.getName());
		result.addProperty("executablePath", currentProgram.getExecutablePath());
		result.addProperty("executableFormat", currentProgram.getExecutableFormat());
		result.addProperty("executableMD5", currentProgram.getExecutableMD5());
		result.addProperty("imageBase", currentProgram.getImageBase().toString());
		result.addProperty("minAddress", currentProgram.getMinAddress().toString());
		result.addProperty("maxAddress", currentProgram.getMaxAddress().toString());
		result.addProperty("languageId", currentProgram.getLanguageID().toString());
		result.addProperty("compilerSpecId", currentProgram.getCompilerSpec().getCompilerSpecID().toString());
		result.add("safety", safetyJson());

		result.add("memoryBlocks", memoryBlocksJson());
		result.add("externalLibraries", externalLibrariesJson());
		result.add("functionSummary", functionSummaryJson());
		result.add("interestingSymbols", interestingSymbolsJson());
		result.add("interestingStrings", interestingStringsJson());

		try (FileWriter writer = new FileWriter(args[0])) {
			Gson gson = new GsonBuilder().setPrettyPrinting().create();
			gson.toJson(result, writer);
		}
		println("Wrote Glyph static summary export to " + args[0]);
	}

	private JsonObject safetyJson() {
		JsonObject safety = new JsonObject();
		safety.addProperty("offlineOnly", true);
		safety.addProperty("debuggerAttach", false);
		safety.addProperty("processMemoryRead", false);
		safety.addProperty("processMemoryDumped", false);
		safety.addProperty("inputSent", false);
		safety.addProperty("credentialExtractionAttempted", false);
		safety.addProperty("promotionPerformed", false);
		return safety;
	}

	private JsonArray memoryBlocksJson() {
		JsonArray blocks = new JsonArray();
		for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
			JsonObject item = new JsonObject();
			item.addProperty("name", block.getName());
			item.addProperty("start", block.getStart().toString());
			item.addProperty("end", block.getEnd().toString());
			item.addProperty("size", block.getSize());
			item.addProperty("read", block.isRead());
			item.addProperty("write", block.isWrite());
			item.addProperty("execute", block.isExecute());
			item.addProperty("initialized", block.isInitialized());
			blocks.add(item);
		}
		return blocks;
	}

	private JsonArray externalLibrariesJson() {
		JsonArray libs = new JsonArray();
		ExternalManager externalManager = currentProgram.getExternalManager();
		for (String name : externalManager.getExternalLibraryNames()) {
			libs.add(name);
		}
		return libs;
	}

	private JsonObject functionSummaryJson() {
		JsonObject summary = new JsonObject();
		JsonArray samples = new JsonArray();
		FunctionIterator functions = currentProgram.getFunctionManager().getFunctions(true);
		int total = 0;
		while (functions.hasNext() && !monitor.isCancelled()) {
			Function function = functions.next();
			total++;
			if (samples.size() < MAX_FUNCTIONS && (matchesKeyword(function.getName()) || samples.size() < 80)) {
				JsonObject item = new JsonObject();
				item.addProperty("name", function.getName());
				item.addProperty("entry", function.getEntryPoint().toString());
				item.addProperty("bodyAddressCount", function.getBody().getNumAddresses());
				item.addProperty("isThunk", function.isThunk());
				item.addProperty("callingConvention", function.getCallingConventionName());
				samples.add(item);
			}
		}
		long instructionCount = 0;
		InstructionIterator instructions = currentProgram.getListing().getInstructions(true);
		while (instructions.hasNext() && !monitor.isCancelled()) {
			instructions.next();
			instructionCount++;
		}
		summary.addProperty("functionCount", total);
		summary.addProperty("instructionCount", instructionCount);
		summary.add("samples", samples);
		return summary;
	}

	private JsonArray interestingSymbolsJson() {
		JsonArray items = new JsonArray();
		SymbolIterator symbols = currentProgram.getSymbolTable().getAllSymbols(true);
		while (symbols.hasNext() && items.size() < MAX_SYMBOLS && !monitor.isCancelled()) {
			Symbol symbol = symbols.next();
			if (!matchesKeyword(symbol.getName())) {
				continue;
			}
			JsonObject item = new JsonObject();
			item.addProperty("name", sanitize(symbol.getName()));
			item.addProperty("address", symbol.getAddress().toString());
			item.addProperty("type", symbol.getSymbolType().toString());
			item.addProperty("source", symbol.getSource().toString());
			items.add(item);
		}
		return items;
	}

	private JsonArray interestingStringsJson() {
		JsonArray items = new JsonArray();
		int scanned = 0;
		for (Data data : DefinedStringIterator.forProgram(currentProgram, currentSelection)) {
			if (monitor.isCancelled()) {
				break;
			}
			scanned++;
			StringDataInstance stringData = StringDataInstance.getStringDataInstance(data);
			String value = stringData.getStringValue();
			if (value == null || value.length() < 4 || !matchesKeyword(value)) {
				continue;
			}
			JsonObject item = new JsonObject();
			item.addProperty("address", data.getAddress().toString());
			item.addProperty("length", value.length());
			item.addProperty("value", sanitize(truncate(value, 500)));
			item.add("references", referencesToJson(data));
			items.add(item);
			if (items.size() >= MAX_STRINGS) {
				break;
			}
		}
		JsonObject countMarker = new JsonObject();
		countMarker.addProperty("scannedStringDataCount", scanned);
		countMarker.addProperty("capturedMarker", true);
		items.add(countMarker);
		return items;
	}

	private JsonArray referencesToJson(Data data) {
		JsonArray refsJson = new JsonArray();
		ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(data.getAddress());
		int count = 0;
		while (refs.hasNext() && count < MAX_REFS_PER_STRING && !monitor.isCancelled()) {
			Reference ref = refs.next();
			JsonObject item = new JsonObject();
			item.addProperty("from", ref.getFromAddress().toString());
			item.addProperty("type", ref.getReferenceType().toString());
			Function function = currentProgram.getFunctionManager().getFunctionContaining(ref.getFromAddress());
			if (function != null) {
				item.addProperty("functionName", function.getName());
				item.addProperty("functionEntry", function.getEntryPoint().toString());
			}
			refsJson.add(item);
			count++;
		}
		return refsJson;
	}

	private boolean matchesKeyword(String value) {
		String lower = value.toLowerCase(Locale.ROOT);
		for (String keyword : KEYWORDS) {
			if (lower.contains(keyword)) {
				return true;
			}
		}
		return false;
	}

	private String sanitize(String value) {
		String redacted = EMAIL_RE.matcher(value).replaceAll("<redacted-email>");
		redacted = BEARER_RE.matcher(redacted).replaceAll("Bearer <redacted>");
		return LONG_VALUE_RE.matcher(redacted).replaceAll("<redacted-long-value>");
	}

	private String truncate(String value, int maxLength) {
		if (value.length() <= maxLength) {
			return value;
		}
		return value.substring(0, maxLength) + "...";
	}
}
